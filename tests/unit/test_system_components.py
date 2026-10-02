"""System components: the parts of a system that deliver its capabilities (ADR-0092)."""

from __future__ import annotations

import io
import json
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureQuery,
)
from smb_requirement_agent.application.ports.catalogue_extractor import (
    ExtractionRequest,
    ExtractionSegment,
    KnownSystem,
)
from smb_requirement_agent.application.ports.catalogue_file import CatalogueFileFormat
from smb_requirement_agent.application.ports.generation_guidance import GenerationGuidance
from smb_requirement_agent.application.use_cases.approval_policy import artifact_fingerprint
from smb_requirement_agent.application.use_cases.resolve_architecture_knowledge import (
    ResolveArchitectureKnowledge,
)
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateContent,
    CandidateDependencyError,
    CandidateKind,
    CandidateMatch,
    apply_candidate,
    classify,
)
from smb_requirement_agent.domain.architecture.diff import ChangedItem, ChangeKind, diff_releases
from smb_requirement_agent.domain.architecture.entities import (
    ArchitectureImpact,
    SystemCapability,
    SystemReference,
)
from smb_requirement_agent.domain.architecture.errors import InvalidArchitectureContentError
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    InvalidKnowledgeError,
    KnowledgeCapability,
    SystemComponent,
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
from smb_requirement_agent.infrastructure.llm.catalogue_extraction import (
    ChangeOutput,
    ExtractionOutput,
    FakeCatalogueExtractor,
    StructuredCatalogueExtractor,
)
from smb_requirement_agent.infrastructure.llm.prompts.catalogue_extraction_prompt import (
    build_user_prompt,
)
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
from smb_requirement_agent.infrastructure.time.fixed_clock import FixedClock
from smb_requirement_agent.interfaces.api.schemas.architecture_knowledge import (
    SystemDefinitionSchema,
)
from tests.unit.test_backlog_export import _document
from tests.unit.test_feature_domain import make_feature

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
ADAPTER = CatalogueFileAdapter()
OWNER = {"X-Fake-Actor-Id": "fake-owner"}

QUOTE_ENGINE = SystemComponent(
    "quote-engine",
    "Quote engine",
    name_ar="محرك العروض",
    description="Prices and issues quotes.",
    aliases=("CPQ",),
    technology="Microservice",
)
ORDER_ENTRY = SystemComponent("order-entry", "Order entry")


def _crm(
    *capabilities: KnowledgeCapability, components: tuple[SystemComponent, ...] = ()
) -> SystemDefinition:
    return SystemDefinition("crm", "CRM", capabilities=capabilities, components=components)


def _release(system: SystemDefinition) -> ArchitectureKnowledge:
    return ArchitectureKnowledge("draft", 1, (system,), ())


QUOTING = KnowledgeCapability("quoting", "Quoting", ("quote",), component_id="quote-engine")


@pytest.mark.parametrize(
    ("build", "message"),
    [
        (lambda: _crm(components=(ORDER_ENTRY, ORDER_ENTRY)), "component ids must be unique"),
        (
            lambda: _crm(components=(QUOTE_ENGINE, SystemComponent("other", "cpq"))),
            "'cpq' names more than one component",
        ),
        (
            lambda: _crm(components=(SystemComponent("x", "X", aliases=("x",)),)),
            "names more than one component",
        ),
        (lambda: _crm(QUOTING, components=(ORDER_ENTRY,)), "Quoting is placed in a component"),
        (lambda: SystemComponent("x", "X", technology=" "), "technology must not be blank"),
        (lambda: KnowledgeCapability("q", "Q", ("q",), component_id=" "), "component"),
    ],
)
def test_a_system_refuses_components_it_cannot_hold(build: Any, message: str) -> None:
    with pytest.raises(InvalidKnowledgeError, match=message):
        build()


def test_capabilities_name_a_component_of_their_own_system() -> None:
    system = _crm(QUOTING, components=(QUOTE_ENGINE, ORDER_ENTRY))

    assert system.component("quote-engine") is QUOTE_ENGINE
    assert system.component(None) is None
    # Removing a component that still holds a capability is refused, so nothing is orphaned.
    with pytest.raises(InvalidKnowledgeError, match="placed in a component"):
        replace(system, components=(ORDER_ENTRY,))
    # Component names never compete with system names: they take no part in matching.
    named_like_a_system = SystemDefinition(
        "billing", "Billing", components=(SystemComponent("crm", "CRM"),)
    )
    ArchitectureKnowledge("draft", 1, (system, named_like_a_system), ())


def test_the_diff_names_component_changes_and_placements() -> None:
    before = _release(_crm(replace(QUOTING, component_id=None), components=(QUOTE_ENGINE,)))
    after = _release(
        _crm(
            QUOTING,
            components=(replace(QUOTE_ENGINE, technology="Batch job", aliases=()), ORDER_ENTRY),
        )
    )

    changes = {(item.item, item.key): item for item in diff_releases(before, after).changes}

    added = changes[(ChangedItem.COMPONENT, "crm/order-entry")]
    assert (added.change, added.label) == (ChangeKind.ADDED, "CRM: Order entry")
    changed = changes[(ChangedItem.COMPONENT, "crm/quote-engine")]
    assert changed.fields == ("aliases", "technology")
    assert changes[(ChangedItem.CAPABILITY, "crm/quoting")].fields == ("component",)
    removed = diff_releases(after, before).changes
    assert any(
        item.item is ChangedItem.COMPONENT and item.change is ChangeKind.REMOVED for item in removed
    )


@pytest.mark.parametrize("file_format", list(CatalogueFileFormat))
def test_every_file_format_keeps_components_and_placements(
    file_format: CatalogueFileFormat,
) -> None:
    release = _release(_crm(QUOTING, components=(QUOTE_ENGINE, ORDER_ENTRY)))

    content = ADAPTER.read(file_format, ADAPTER.write(file_format, release))

    assert content.systems == release.systems


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


def test_older_files_import_and_unknown_components_are_named() -> None:
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
    assert old.systems[0].components == ()
    assert old.systems[0].capabilities[0].component_id is None
    assert ADAPTER.read(CatalogueFileFormat.YAML, b"systems:\n  - id: crm\n    name: CRM\n")

    with pytest.raises(InvalidKnowledgeError, match="Systems row 2: CRM: Q is placed"):
        ADAPTER.read(
            CatalogueFileFormat.XLSX,
            _workbook(
                Systems=systems,
                Capabilities=[
                    ("system_id", "capability_id", "name", "triggers", "component_id"),
                    ("crm", "q", "Q", "q", "ghost"),
                ],
            ),
        )
    with pytest.raises(InvalidKnowledgeError, match="Components row 2: system 'erp'"):
        ADAPTER.read(
            CatalogueFileFormat.XLSX,
            _workbook(
                Systems=systems,
                Components=[("system_id", "component_id", "name"), ("erp", "ui", "UI")],
            ),
        )
    with pytest.raises(InvalidKnowledgeError, match="systems entry 1, component 1: name"):
        ADAPTER.read(
            CatalogueFileFormat.JSON,
            json.dumps(
                {"systems": [{"id": "crm", "name": "CRM", "components": [{"id": "x"}]}]}
            ).encode(),
        )


def _resolver(release: ArchitectureKnowledge) -> ResolveArchitectureKnowledge:
    return ResolveArchitectureKnowledge(
        InMemoryArchitectureKnowledgeRepository(release),
        InMemoryEvidenceIndex(FakeEmbeddings(), FakeWordTokenizer()),
        FakeArchitectureReasoner(),
        YamlArchitectureKnowledge(default_knowledge_path()),
        InMemoryOrganisationRepository(FixedClock(NOW)),
    )


def test_mapping_shows_the_component_that_delivers_each_capability() -> None:
    seed = seed_knowledge()
    bcrm = next(item for item in seed.systems if item.id == "bcrm")
    placed = replace(
        bcrm,
        components=(QUOTE_ENGINE,),
        capabilities=(replace(bcrm.capabilities[0], component_id="quote-engine"),),
    )
    release = replace(
        seed, systems=tuple(placed if item.id == "bcrm" else item for item in seed.systems)
    )

    mapped = _resolver(release).match(ArchitectureQuery(text=("The assisted sales journey",)))
    plain = _resolver(seed).match(ArchitectureQuery(text=("The assisted sales journey",)))

    capability = mapped.systems[0].capabilities[0]
    assert (capability.component_id, capability.component_name) == ("quote-engine", "Quote engine")
    assert plain.systems[0].capabilities[0].component_id is None
    # Show-only: which systems are mapped does not change.
    assert [item.id for item in mapped.systems] == [item.id for item in plain.systems]


def _impact(capability: SystemCapability) -> ArchitectureImpact:
    return ArchitectureImpact("v1", NOW, (SystemReference("crm", "CRM", True, (capability,)),))


def test_components_on_impacts_persist_and_stay_out_of_fingerprints_and_prompts() -> None:
    placed = _impact(SystemCapability("quote", "Quote", component_id="qe", component_name="QE"))
    bare = _impact(SystemCapability("quote", "Quote"))

    assert architecture_from_payload(architecture_to_payload(placed)) == placed
    legacy = architecture_to_payload(bare)
    assert isinstance(legacy, dict)
    assert legacy["systems"][0]["capabilities"] == [{"id": "quote", "name": "Quote"}]
    feature = make_feature()
    assert artifact_fingerprint(feature.with_architecture(placed)) == artifact_fingerprint(
        feature.with_architecture(bare)
    )
    assert render_guidance(
        GenerationGuidance(architecture=ArchitectureKnowledgeMatch("v1", placed.systems, ()))
    ) == render_guidance(
        GenerationGuidance(architecture=ArchitectureKnowledgeMatch("v1", bare.systems, ()))
    )
    with pytest.raises(InvalidArchitectureContentError, match="needs its name"):
        SystemCapability("quote", "Quote", component_id="qe")


def test_component_suggestions_add_or_fill_in_without_moving_capabilities() -> None:
    draft = _release(_crm(KnowledgeCapability("quoting", "Quoting", ("quote",))))
    component = CandidateContent(
        CandidateKind.COMPONENT,
        "crm",
        name="Quote engine",
        component_id="quote-engine",
        aliases=("CPQ",),
        technology="Microservice",
    )
    capability = CandidateContent(
        CandidateKind.CAPABILITY,
        "crm",
        name="Quoting",
        capability_id="quoting",
        triggers=("quote",),
        component_id="quote-engine",
    )

    assert classify(component, draft) is CandidateMatch.NEW
    assert classify(capability, draft) is CandidateMatch.NEEDS_COMPONENT
    with pytest.raises(CandidateDependencyError, match="component 'quote-engine' of CRM"):
        apply_candidate(capability, draft)

    with_component = apply_candidate(component, draft)
    added = with_component.systems[0].components[0]
    assert (added.name, added.aliases, added.technology) == (
        "Quote engine",
        ("CPQ",),
        "Microservice",
    )
    assert classify(component, with_component) is CandidateMatch.ALREADY_PRESENT
    # A capability with no component is placed by a suggestion that names one.
    assert classify(capability, with_component) is CandidateMatch.UPDATES_EXISTING
    placed = apply_candidate(capability, with_component)
    assert placed.systems[0].capabilities[0].component_id == "quote-engine"
    assert classify(capability, placed) is CandidateMatch.ALREADY_PRESENT

    # Filling in: an empty description is added, an existing technology is kept.
    described = replace(component, description="Prices quotes.", technology="Batch job")
    assert classify(described, placed) is CandidateMatch.UPDATES_EXISTING
    filled = apply_candidate(described, placed).systems[0].components[0]
    assert (filled.description, filled.technology) == ("Prices quotes.", "Microservice")

    # Never moving: a capability already in a component stays there.
    other = apply_candidate(
        CandidateContent(CandidateKind.COMPONENT, "crm", name="Order entry", component_id="oe"),
        placed,
    )
    moved = apply_candidate(replace(capability, component_id="oe", triggers=("price",)), other)
    assert moved.systems[0].capabilities[0].component_id == "quote-engine"


def test_candidate_content_keeps_component_fields_to_their_kinds() -> None:
    with pytest.raises(InvalidKnowledgeError, match="Only a component or a capability"):
        CandidateContent(CandidateKind.CONSTRAINT, "crm", text="x", component_id="qe")
    with pytest.raises(InvalidKnowledgeError, match="Only a component has"):
        CandidateContent(CandidateKind.SYSTEM, "crm", name="CRM", technology="SaaS")
    with pytest.raises(InvalidKnowledgeError, match="Component id"):
        CandidateContent(CandidateKind.COMPONENT, "crm", name="UI")


def _change(**values: Any) -> ChangeOutput:
    defaults: dict[str, Any] = {
        "kind": "component",
        "system": "BCRM",
        "name": "Quote engine",
        "name_ar": None,
        "aliases": [],
        "triggers": [],
        "target_system": None,
        "component": None,
        "technology": "Microservice",
        "domain": None,
        "parent_domain": None,
        "offering": None,
        "journey": None,
        "text": "Prices and issues quotes.",
        "evidence_numbers": [1],
        "quote": "The quote engine prices quotes",
        "basis": "stated",
        "reasoning": None,
        "relationship_kind": None,
    }
    return ChangeOutput(**(defaults | values))


class _Client:
    model = "test-model"

    def __init__(self, output: ExtractionOutput) -> None:
        self.output = output

    def parse(self, **_: Any) -> Any:
        return self.output


def test_reading_proposes_components_and_where_capabilities_belong() -> None:
    request = ExtractionRequest(
        "Design",
        (
            ExtractionSegment(
                1, "paragraph 1", "In BCRM the quote engine prices quotes for sales agents."
            ),
        ),
        (KnownSystem("bcrm", "BCRM", (), ("Order entry",)),),
    )
    client = _Client(
        ExtractionOutput(
            changes=[
                _change(),
                _change(
                    kind="capability",
                    name="Quoting",
                    triggers=["price a quote"],
                    component="Quote engine",
                    technology=None,
                    text=None,
                ),
            ]
        )
    )

    proposal = StructuredCatalogueExtractor(client, supports_images=False).propose(request)

    component, capability = (item.content for item in proposal.changes)
    assert (component.kind, component.system_id, component.component_id) == (
        CandidateKind.COMPONENT,
        "bcrm",
        "quote-engine",
    )
    assert (component.description, component.technology) == (
        "Prices and issues quotes.",
        "Microservice",
    )
    assert capability.component_id == "quote-engine"
    assert json.loads(build_user_prompt(request))["known_systems"][0]["components"] == [
        "Order entry"
    ]


def test_the_offline_reader_recognises_component_lines() -> None:
    text = (
        "System: Order Hub\n"
        "Component: Order API [Microservice]\n"
        "Capability: Order capture (capture order) @ Order API\n"
    )
    proposal = FakeCatalogueExtractor().propose(
        ExtractionRequest("Design", (ExtractionSegment(1, "lines 1-3", text),), ())
    )

    _, component, capability = (item.content for item in proposal.changes)
    assert (component.kind, component.component_id, component.technology) == (
        CandidateKind.COMPONENT,
        "order-api",
        "Microservice",
    )
    assert capability.component_id == "order-api"


SOURCE = b"""System: Order Hub
Component: Order API [Microservice]
Capability: Order capture (capture order, new order) @ Order API
"""


def test_suggested_components_are_accepted_before_their_capabilities(client: TestClient) -> None:
    draft = client.post(
        "/architecture-knowledge/releases", json={"name": "Components"}, headers=OWNER
    ).json()
    base = f"/architecture-knowledge/releases/{draft['id']}"
    uploaded = client.post(
        f"{base}/documents",
        data={"title": "Order Hub", "language": "en", "expected_revision": draft["revision"]},
        files={"file": ("design.txt", SOURCE, "text/plain")},
        headers=OWNER,
    )
    assert uploaded.status_code == 201, uploaded.text
    version_id = uploaded.json()["documents"][-1]["id"]
    client.post(f"{base}/documents/{version_id}/extractions", headers=OWNER)
    listing = client.get(f"{base}/suggestions", headers=OWNER).json()
    by_kind = {item["content"]["kind"]: item for item in listing["suggestions"]}
    assert by_kind["component"]["content"]["technology"] == "Microservice"
    accepted = client.post(
        f"{base}/suggestions/{by_kind['system']['id']}/decision",
        json={"expected_revision": listing["release_revision"], "accept": True},
        headers=OWNER,
    )
    assert accepted.status_code == 200, accepted.text
    middle = client.get(f"{base}/suggestions", headers=OWNER).json()["suggestions"]
    assert (
        next(item for item in middle if item["content"]["kind"] == "capability")["match"]
        == "needs_component"
    )

    rest = client.post(
        f"{base}/suggestions/acceptance",
        json={"expected_revision": accepted.json()["revision"]},
        headers=OWNER,
    ).json()

    assert rest["remaining"] == 0
    order_hub = next(item for item in rest["release"]["systems"] if item["id"] == "order-hub")
    assert [item["id"] for item in order_hub["components"]] == ["order-api"]
    assert order_hub["capabilities"][0]["component_id"] == "order-api"


def test_the_api_round_trips_components_and_older_clients_keep_working() -> None:
    system = _crm(QUOTING, components=(QUOTE_ENGINE,))

    schema = SystemDefinitionSchema.from_domain(system)

    assert SystemDefinitionSchema.model_validate(schema.model_dump()).to_domain() == system
    older = SystemDefinitionSchema.model_validate({"id": "crm", "name": "CRM"}).to_domain()
    assert older.components == ()


def test_exports_carry_the_capability_component() -> None:
    document = _document("owner")
    feature = document.epic.features[0]
    assert feature.architecture is not None
    system = feature.architecture.systems[0]
    with_component = replace(
        system,
        capabilities=(replace(system.capabilities[0], component="Quote engine"),),
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
                        systems=(with_component, *feature.architecture.systems[1:]),
                    ),
                ),
            ),
        ),
    )

    workbook = load_workbook(io.BytesIO(XlsxBacklogExporter().render(document)))
    header = [cell.value for cell in workbook["Systems"][1]]
    row = next(workbook["Systems"].iter_rows(min_row=2, values_only=True))
    capability_name = system.capabilities[0].name
    assert row[header.index("capability_components")] == f"{capability_name}: Quote engine"
    payload = json.loads(JsonBacklogExporter().render(document))
    capability = payload["epic"]["features"][0]["architecture"]["systems"][0]["capabilities"][0]
    assert capability["component"] == "Quote engine"
