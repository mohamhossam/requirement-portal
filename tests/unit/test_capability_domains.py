"""Capability domains: a shallow business taxonomy for the catalogue (ADR-0089)."""

from __future__ import annotations

import io
import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from openpyxl import Workbook, load_workbook
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureQuery,
)
from smb_requirement_agent.application.ports.catalogue_file import CatalogueFileFormat
from smb_requirement_agent.application.ports.generation_guidance import GenerationGuidance
from smb_requirement_agent.application.use_cases.approval_policy import artifact_fingerprint
from smb_requirement_agent.application.use_cases.capability_domain_fallback import (
    suggest_domains,
)
from smb_requirement_agent.application.use_cases.resolve_architecture_knowledge import (
    ResolveArchitectureKnowledge,
)
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateContent,
    CandidateKind,
    apply_candidate,
)
from smb_requirement_agent.domain.architecture.diff import ChangedItem, ChangeKind, diff_releases
from smb_requirement_agent.domain.architecture.entities import (
    ArchitectureImpact,
    DomainSuggestion,
    SystemCapability,
    SystemReference,
)
from smb_requirement_agent.domain.architecture.errors import InvalidArchitectureContentError
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    CapabilityDomain,
    InvalidKnowledgeError,
    KnowledgeCapability,
    KnowledgeReleaseStatus,
    SystemDefinition,
)
from smb_requirement_agent.infrastructure.architecture.catalogue_files import CatalogueFileAdapter
from smb_requirement_agent.infrastructure.architecture.embeddings import FakeEmbeddings
from smb_requirement_agent.infrastructure.architecture.evidence_index import (
    InMemoryEvidenceIndex,
)
from smb_requirement_agent.infrastructure.architecture.knowledge_yaml import seed_knowledge
from smb_requirement_agent.infrastructure.architecture.reasoning import FakeArchitectureReasoner
from smb_requirement_agent.infrastructure.architecture.tokenizer import FakeWordTokenizer
from smb_requirement_agent.infrastructure.architecture.yaml_knowledge import (
    YamlArchitectureKnowledge,
    default_knowledge_path,
)
from smb_requirement_agent.infrastructure.exports.json_exporter import JsonBacklogExporter
from smb_requirement_agent.infrastructure.exports.xlsx_exporter import XlsxBacklogExporter
from smb_requirement_agent.infrastructure.llm.prompts.generation_guidance import render_guidance
from smb_requirement_agent.infrastructure.persistence.in_memory_architecture_knowledge import (
    InMemoryArchitectureKnowledgeRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_organisation import (
    InMemoryOrganisationRepository,
)
from smb_requirement_agent.infrastructure.persistence.shared_payloads import (
    architecture_from_payload,
    architecture_to_payload,
)
from tests.unit.test_backlog_export import _document
from tests.unit.test_feature_domain import make_feature

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
ADAPTER = CatalogueFileAdapter()


def _release(
    domains: tuple[CapabilityDomain, ...], *capabilities: KnowledgeCapability
) -> ArchitectureKnowledge:
    return ArchitectureKnowledge(
        "draft",
        1,
        (SystemDefinition("crm", "CRM", capabilities=capabilities),),
        (),
        capability_domains=domains,
    )


ORDERS = CapabilityDomain("orders", "Order capture", name_ar="استلام الطلبات")
QUOTES = CapabilityDomain("quotes", "Quoting", parent_id="orders")


@pytest.mark.parametrize(
    ("domains", "message"),
    [
        ((ORDERS, ORDERS), "ids must be unique"),
        ((QUOTES,), "parent that is not in the catalogue"),
        (
            (
                CapabilityDomain("a", "A", parent_id="b"),
                CapabilityDomain("b", "B", parent_id="a"),
            ),
            "inside itself",
        ),
        (
            (
                ORDERS,
                QUOTES,
                CapabilityDomain("q2", "Deal desk", parent_id="quotes"),
                CapabilityDomain("q3", "Pricing", parent_id="q2"),
            ),
            "at most 3 levels",
        ),
        ((ORDERS, QUOTES, CapabilityDomain("q2", "quoting", parent_id="orders")), "named"),
    ],
)
def test_the_domain_tree_refuses_what_it_cannot_hold(
    domains: tuple[CapabilityDomain, ...], message: str
) -> None:
    with pytest.raises(InvalidKnowledgeError, match=message):
        _release(domains)


def test_a_capability_names_a_domain_the_release_has() -> None:
    placed = KnowledgeCapability("quote", "Quote", ("quote",), "quotes")

    release = _release((ORDERS, QUOTES), placed)

    assert [item.name for item in release.domain_path("quotes")] == ["Order capture", "Quoting"]
    assert release.domain_path(None) == ()
    with pytest.raises(InvalidKnowledgeError, match="not in the catalogue"):
        _release((ORDERS,), placed)
    with pytest.raises(InvalidKnowledgeError, match="not in the catalogue"):
        replace(release, capability_domains=(ORDERS,))


def test_the_seed_places_every_capability_in_one_of_eight_domains() -> None:
    seed = seed_knowledge()

    assert len(seed.capability_domains) == 8
    assert all(cap.domain_id for system in seed.systems for cap in system.capabilities)
    bcrm = next(item for item in seed.systems if item.id == "bcrm")
    assert [item.name for item in seed.domain_path(bcrm.capabilities[0].domain_id)] == [
        "Order capture"
    ]


def test_the_diff_names_domain_and_placement_changes() -> None:
    base = seed_knowledge()
    first, *rest = base.systems
    moved = replace(first, capabilities=(replace(first.capabilities[0], domain_id="billing"),))
    renamed = tuple(
        replace(item, name="Order taking") if item.id == "order-capture" else item
        for item in base.capability_domains
    )
    draft = replace(
        base,
        id="draft",
        systems=(moved, *rest),
        capability_domains=(*renamed, CapabilityDomain("partners", "Partners")),
    )

    found = {
        (item.item, item.change, item.key): item for item in diff_releases(base, draft).changes
    }

    capability = f"{first.id}/{first.capabilities[0].id}"
    assert found[(ChangedItem.CAPABILITY, ChangeKind.CHANGED, capability)].fields == ("domain",)
    assert found[(ChangedItem.DOMAIN, ChangeKind.CHANGED, "order-capture")].fields == ("name",)
    assert (ChangedItem.DOMAIN, ChangeKind.ADDED, "partners") in found


@pytest.mark.parametrize("file_format", list(CatalogueFileFormat))
def test_every_file_format_keeps_domains_and_placements(file_format: CatalogueFileFormat) -> None:
    seed = replace(
        seed_knowledge(),
        capability_domains=(
            *seed_knowledge().capability_domains,
            CapabilityDomain("quotes", "Quoting", "التسعير", "order-capture", "Price quotes"),
        ),
    )

    content = ADAPTER.read(file_format, ADAPTER.write(file_format, seed))

    assert content.capability_domains == seed.capability_domains
    assert content.systems == seed.systems


def _workbook(**sheets: list[tuple[object, ...]]) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.worksheets[0])
    for name, rows in sheets.items():
        sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(list(row))
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_workbooks_without_domains_import_and_unknown_placements_are_named() -> None:
    systems: list[tuple[object, ...]] = [("system_id", "name"), ("crm", "CRM")]
    old = ADAPTER.read(
        CatalogueFileFormat.XLSX,
        _workbook(
            Systems=systems,
            Capabilities=[
                ("system_id", "capability_id", "name", "triggers"),
                ("crm", "q", "Q", "q"),
            ],
        ),
    )
    assert old.capability_domains == ()
    assert old.systems[0].capabilities[0].domain_id is None

    with pytest.raises(InvalidKnowledgeError, match="domain 'sales' is not listed"):
        ADAPTER.read(
            CatalogueFileFormat.XLSX,
            _workbook(
                Systems=systems,
                Capabilities=[
                    ("system_id", "capability_id", "name", "triggers", "domain_id"),
                    ("crm", "q", "Q", "q", "sales"),
                ],
            ),
        )


def test_suggestions_come_from_catalogue_words_one_per_branch() -> None:
    release = ArchitectureKnowledge(
        "draft",
        1,
        (
            SystemDefinition(
                "crm",
                "CRM",
                capabilities=(KnowledgeCapability("quote", "Quote", ("price quote",), "quotes"),),
            ),
            SystemDefinition(
                "bill",
                "Billing",
                capabilities=(KnowledgeCapability("inv", "Invoicing", ("invoice",), "billing"),),
            ),
        ),
        (),
        capability_domains=(ORDERS, QUOTES, CapabilityDomain("billing", "Billing")),
    )

    broad = suggest_domains(release, "Improve order capture: send a price quote and invoice")
    narrow = suggest_domains(release, "Send a price quote, then an invoice")

    # A parent gathers its children's words, so naming it outranks the child it holds.
    assert [(item.domain_id, item.path) for item in broad] == [
        ("orders", ("Order capture",)),
        ("billing", ("Billing",)),
    ]
    assert broad[0].matched_terms == ("Order capture", "Quote", "price quote")
    # Otherwise the more specific domain wins, and its parent is not repeated.
    assert [(item.domain_id, item.path) for item in narrow] == [
        ("quotes", ("Order capture", "Quoting")),
        ("billing", ("Billing",)),
    ]
    assert narrow[0].system_ids == ("crm",)
    assert suggest_domains(release, "استلام الطلبات للعملاء")[0].domain_id == "orders"
    assert suggest_domains(release, "Nothing that matches") == ()
    assert suggest_domains(release, "Improve order capture") == suggest_domains(
        release, "Improve order capture"
    )


def _resolver() -> ResolveArchitectureKnowledge:
    return ResolveArchitectureKnowledge(
        InMemoryArchitectureKnowledgeRepository(seed_knowledge()),
        InMemoryEvidenceIndex(FakeEmbeddings(), FakeWordTokenizer()),
        FakeArchitectureReasoner(),
        YamlArchitectureKnowledge(default_knowledge_path()),
        InMemoryOrganisationRepository(FixedClock(NOW)),
    )


def test_mapping_places_capabilities_and_suggests_domains_only_when_nothing_mapped() -> None:
    mapped = _resolver().match(ArchitectureQuery(text=("The assisted sales journey",)))
    unmapped = _resolver().match(
        ArchitectureQuery(text=("Speed up billing for small business orders",))
    )

    assert mapped.systems[0].capabilities[0].domain_path == ("Order capture",)
    assert mapped.suggested_domains == ()
    assert unmapped.systems == ()
    assert [item.path for item in unmapped.suggested_domains] == [("Billing",)]
    assert unmapped.suggested_domains[0].system_ids == ("bscs",)
    assert unmapped.suggested_domains[0].system_names == ("BSCS",)


def _impact(**changes: object) -> ArchitectureImpact:
    base = ArchitectureImpact(
        "v1",
        NOW,
        (
            SystemReference(
                "crm",
                "CRM",
                True,
                (SystemCapability("quote", "Quote", "quotes", ("Order capture", "Quoting")),),
            ),
        ),
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def test_domains_on_impacts_persist_and_stay_out_of_fingerprints_and_prompts() -> None:
    impact = _impact()
    bare = replace(
        impact,
        systems=(replace(impact.systems[0], capabilities=(SystemCapability("quote", "Quote"),)),),
    )
    suggested = ArchitectureImpact(
        "v1",
        NOW,
        (),
        suggested_domains=(DomainSuggestion("billing", ("Billing",), ("bscs",), ("billing",)),),
    )

    assert architecture_from_payload(architecture_to_payload(impact)) == impact
    assert architecture_from_payload(architecture_to_payload(suggested)) == suggested
    legacy = architecture_to_payload(bare)
    assert isinstance(legacy, dict)
    assert legacy["systems"][0]["capabilities"] == [{"id": "quote", "name": "Quote"}]
    assert "suggested_domains" not in legacy

    feature = make_feature()
    assert artifact_fingerprint(feature.with_architecture(impact)) == artifact_fingerprint(
        feature.with_architecture(bare)
    )
    match = ArchitectureKnowledgeMatch(
        "v1", impact.systems, (), suggested_domains=suggested.suggested_domains
    )
    plain = ArchitectureKnowledgeMatch("v1", bare.systems, ())
    assert render_guidance(GenerationGuidance(architecture=match)) == render_guidance(
        GenerationGuidance(architecture=plain)
    )
    with pytest.raises(InvalidArchitectureContentError, match="no catalogued system"):
        replace(impact, suggested_domains=suggested.suggested_domains)
    with pytest.raises(InvalidArchitectureContentError, match="needs its path"):
        SystemCapability("quote", "Quote", "quotes")


def test_a_capability_suggestion_keeps_the_domain_it_was_placed_in() -> None:
    draft = replace(
        seed_knowledge(),
        id="draft",
        status=KnowledgeReleaseStatus.DRAFT,
        published_at=None,
        published_by=None,
    )
    bcrm = next(item for item in draft.systems if item.id == "bcrm")
    capability = bcrm.capabilities[0]

    updated = apply_candidate(
        CandidateContent(
            CandidateKind.CAPABILITY,
            "bcrm",
            name=capability.name,
            capability_id=capability.id,
            triggers=("new phrase",),
        ),
        draft,
    )

    merged = next(item for item in updated.systems if item.id == "bcrm").capabilities[0]
    assert "new phrase" in merged.triggers
    assert merged.domain_id == capability.domain_id


def test_exports_carry_the_capability_domain() -> None:
    document = _document("owner")
    feature = document.epic.features[0]
    assert feature.architecture is not None
    system = feature.architecture.systems[0]
    with_domain = replace(
        system,
        capabilities=(replace(system.capabilities[0], domain_path=("Order capture", "Quoting")),),
    )
    document = replace(
        document,
        epic=replace(
            document.epic,
            features=(
                replace(
                    feature,
                    architecture=replace(
                        feature.architecture,
                        systems=(with_domain, *feature.architecture.systems[1:]),
                    ),
                ),
            ),
        ),
    )

    workbook = load_workbook(io.BytesIO(XlsxBacklogExporter().render(document)))
    header = [cell.value for cell in workbook["Systems"][1]]
    row = next(workbook["Systems"].iter_rows(min_row=2, values_only=True))
    assert row[header.index("capability_domains")] == "Order capture > Quoting"
    payload = json.loads(JsonBacklogExporter().render(document))
    capability = payload["epic"]["features"][0]["architecture"]["systems"][0]["capabilities"][0]
    assert capability["domain_path"] == ["Order capture", "Quoting"]
