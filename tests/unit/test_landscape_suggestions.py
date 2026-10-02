"""Readings suggest landscape domains, where each system sits and what it is for (ADR-0094).

The reported gap: a landscape document's Domains table, the domain heading above
each systems table, its Sub-domain column and each system's Function were read
and then dropped.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.ports.catalogue_extractor import (
    ExtractionRequest,
    ExtractionSegment,
)
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateCitation,
    CandidateContent,
    CandidateKind,
    CandidateMatch,
    CandidateStatus,
    CatalogueCandidate,
    apply_candidate,
    classify,
    needs_one_by_one,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    InvalidKnowledgeError,
    LandscapeDomain,
    SystemDefinition,
)
from smb_requirement_agent.infrastructure.architecture.catalogue_tables import (
    CatalogueTableReader,
)
from smb_requirement_agent.infrastructure.architecture.markdown_passages import markdown_passages
from smb_requirement_agent.infrastructure.llm.catalogue_extraction import (
    ChangeOutput,
    ExtractionOutput,
    StructuredCatalogueExtractor,
)
from smb_requirement_agent.infrastructure.llm.prompts.catalogue_extraction_prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "catalogue" / "synthetic_landscape.md"
OWNER = {"X-Fake-Actor-Id": "fake-owner"}
NOW = datetime(2026, 10, 1, tzinfo=UTC)
CUSTOMER = LandscapeDomain("customer", "Customer")


def _draft(*domains: LandscapeDomain, systems: tuple[SystemDefinition, ...] = ()) -> Any:
    return ArchitectureKnowledge(
        "draft",
        1,
        systems or (SystemDefinition("cim", "CIM"),),
        (),
        landscape_domains=domains,
    )


def _domain(domain_id: str, name: str, parent: str | None = None, **values: Any) -> Any:
    return CandidateContent(
        CandidateKind.LANDSCAPE_DOMAIN,
        domain_id,
        name=name,
        landscape_domain_id=domain_id,
        parent_domain_id=parent,
        **values,
    )


def _place(system: str, domain: str) -> CandidateContent:
    return CandidateContent(CandidateKind.PLACEMENT, system, landscape_domain_id=domain)


# Domain -----------------------------------------------------------------------------------


def test_a_suggested_domain_is_new_waits_for_its_parent_or_fills_a_gap() -> None:
    assisted = _domain("customer-assisted", "Assisted", "customer")

    assert classify(_domain("customer", "Customer"), _draft()) is CandidateMatch.NEW
    assert classify(assisted, _draft()) is CandidateMatch.NEEDS_DOMAIN
    assert classify(assisted, _draft(CUSTOMER)) is CandidateMatch.NEW
    # The same name under the same parent is that domain, whatever key it was given.
    named = _draft(CUSTOMER, LandscapeDomain("assisted-desk", "Assisted", parent_id="customer"))
    assert classify(assisted, named) is CandidateMatch.ALREADY_PRESENT
    described = _domain("customer", "Customer", description="TAM · Customer")
    assert classify(described, _draft(CUSTOMER)) is CandidateMatch.UPDATES_EXISTING

    added = apply_candidate(assisted, _draft(CUSTOMER))
    assert [item.id for item in added.landscape_domains] == ["customer", "customer-assisted"]
    assert apply_candidate(described, _draft(CUSTOMER)).landscape_domains[0].description == (
        "TAM · Customer"
    )


def test_a_placement_needs_its_system_and_domain_and_moving_one_is_decided_alone() -> None:
    assert classify(_place("cim", "customer"), _draft()) is CandidateMatch.NEEDS_DOMAIN
    assert classify(_place("ghost", "customer"), _draft(CUSTOMER)) is CandidateMatch.NEEDS_SYSTEM
    assert classify(_place("cim", "customer"), _draft(CUSTOMER)) is CandidateMatch.NEW
    # A bare name finds the one domain that has it.
    placed = apply_candidate(_place("cim", "Customer"), _draft(CUSTOMER))
    assert placed.systems[0].landscape_domain_id == "customer"
    assert classify(_place("cim", "customer"), placed) is CandidateMatch.ALREADY_PRESENT

    resource = LandscapeDomain("resource", "Resource")
    elsewhere = _draft(
        CUSTOMER,
        resource,
        systems=(SystemDefinition("cim", "CIM", landscape_domain_id="resource"),),
    )
    move = CatalogueCandidate(
        "c1",
        "draft",
        "doc",
        _place("cim", "customer"),
        (CandidateCitation("line 4", "CIM | Customer"),),
        "reader",
        "v1",
        NOW,
    )
    assert classify(move.content, elsewhere) is CandidateMatch.UPDATES_EXISTING
    assert needs_one_by_one(move, elsewhere)
    assert not needs_one_by_one(move, _draft(CUSTOMER))


def test_a_suggested_description_fills_a_gap_and_never_replaces_one() -> None:
    suggested = CandidateContent(
        CandidateKind.SYSTEM, "cim", name="CIM", description="Agent screen for care."
    )

    assert classify(suggested, _draft()) is CandidateMatch.UPDATES_EXISTING
    assert apply_candidate(suggested, _draft()).systems[0].description == "Agent screen for care."
    kept = _draft(systems=(SystemDefinition("cim", "CIM", description="Care desk."),))
    assert classify(suggested, kept) is CandidateMatch.ALREADY_PRESENT
    assert apply_candidate(suggested, kept).systems[0].description == "Care desk."


def test_only_domain_suggestions_carry_domain_fields() -> None:
    with pytest.raises(InvalidKnowledgeError, match="Only a landscape domain or a placement"):
        CandidateContent(CandidateKind.SYSTEM, "cim", name="CIM", landscape_domain_id="customer")
    with pytest.raises(InvalidKnowledgeError, match="Landscape domain must not be blank"):
        CandidateContent(CandidateKind.PLACEMENT, "cim")
    with pytest.raises(InvalidKnowledgeError, match="cannot be its own parent"):
        _domain("customer", "Customer", "customer")


# Reading ----------------------------------------------------------------------------------


def _request(text: str) -> ExtractionRequest:
    segments = tuple(
        ExtractionSegment(
            number, item.location, item.text, section=item.heading_path, cells=item.cells
        )
        for number, item in enumerate(markdown_passages(text), 1)
    )
    return ExtractionRequest("Landscape", segments, ())


def test_tables_give_the_domains_where_each_system_sits_and_what_it_is_for() -> None:
    reading = CatalogueTableReader().read(_request(FIXTURE.read_text(encoding="utf-8")))

    domains = [
        (item.content.landscape_domain_id, item.content.name, item.content.parent_domain_id)
        for item in reading.changes
        if item.content.kind is CandidateKind.LANDSCAPE_DOMAIN
    ]
    assert domains == [
        ("ordering", "Ordering", None),
        ("fulfilment", "Fulfilment", None),
        ("ordering-un-assisted", "Un-assisted", "ordering"),
        ("ordering-data-case", "Data & Case", "ordering"),
    ]
    placed = {
        item.content.system_id: item.content.landscape_domain_id
        for item in reading.changes
        if item.content.kind is CandidateKind.PLACEMENT
    }
    assert placed == {
        "order-portal": "ordering-un-assisted",
        "order-gateway": "ordering-data-case",
        "pricing-engine": "ordering",
        "flow-engine": "fulfilment",
        "field-desk": "fulfilment",
        "notifier": "fulfilment",
    }
    described = {
        item.content.system_id: item.content.description
        for item in reading.changes
        if item.content.kind is CandidateKind.SYSTEM
    }
    assert described["notifier"] == "Template-driven SMS and email notifications."
    # The Domains table's code is the domain's description.
    first = next(item for item in reading.changes if item.content.landscape_domain_id == "ordering")
    assert first.content.description == "TAM · Ordering"


def test_a_domain_column_places_a_system_even_without_a_domains_table() -> None:
    text = (
        "| System | ID | Domain |\n|---|---|---|\n"
        "| Care Desk | SYS-CARE | Customer |\n| Ledger | SYS-LEDGER | Customer |\n"
    )

    reading = CatalogueTableReader().read(_request(text))

    kinds = [(item.content.kind, item.content.landscape_domain_id) for item in reading.changes]
    assert kinds.count((CandidateKind.LANDSCAPE_DOMAIN, "customer")) == 1
    assert kinds.count((CandidateKind.PLACEMENT, "customer")) == 2


# The model --------------------------------------------------------------------------------


class _Answer:
    model = "scripted"

    def __init__(self, output: ExtractionOutput) -> None:
        self.output = output

    def parse(self, **_: Any) -> ExtractionOutput:
        return self.output


def _change(**values: Any) -> ChangeOutput:
    base: dict[str, Any] = {
        "kind": "landscape_domain",
        "system": "",
        "name": "Assisted",
        "name_ar": None,
        "aliases": [],
        "triggers": [],
        "target_system": None,
        "component": None,
        "technology": None,
        "domain": None,
        "parent_domain": "Customer",
        "offering": None,
        "journey": None,
        "text": "Agent-facing channels.",
        "evidence_numbers": [1],
        "quote": "CIM sits in the assisted channels of the Customer domain",
        "basis": "stated",
        "reasoning": None,
        "relationship_kind": None,
    }
    return ChangeOutput(**(base | values))


def test_the_model_suggests_domains_and_placements_from_prose() -> None:
    passage = "CIM sits in the assisted channels of the Customer domain, as the agent screen."
    output = ExtractionOutput(
        changes=[
            _change(),
            _change(kind="placement", system="CIM", name=None, domain="Assisted", text=None),
        ]
    )
    client: Any = _Answer(output)

    domain, placement = (
        StructuredCatalogueExtractor(client, supports_images=False)
        .propose(ExtractionRequest("Notes", (ExtractionSegment(1, "paragraph 1", passage),), ()))
        .changes
    )

    assert (domain.content.landscape_domain_id, domain.content.parent_domain_id) == (
        "customer-assisted",
        "customer",
    )
    assert domain.content.description == "Agent-facing channels."
    assert (placement.content.system_id, placement.content.landscape_domain_id) == (
        "cim",
        "customer-assisted",
    )
    assert PROMPT_VERSION == "catalogue-extraction-v10"
    assert "landscape_domain: an area of the architecture landscape" in SYSTEM_PROMPT
    assert "placement: one system sitting in one landscape domain" in SYSTEM_PROMPT


# End to end -------------------------------------------------------------------------------


def test_accepting_a_landscape_document_places_and_describes_its_systems(
    client: TestClient,
) -> None:
    draft = client.post(
        "/architecture-knowledge/releases", json={"name": "Next version"}, headers=OWNER
    ).json()
    uploaded = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/documents",
        data={"title": "Landscape", "language": "en", "expected_revision": draft["revision"]},
        files={"file": ("landscape.md", FIXTURE.read_bytes(), "text/markdown")},
        headers=OWNER,
    ).json()
    base = f"/architecture-knowledge/releases/{draft['id']}"
    client.post(f"{base}/documents/{uploaded['documents'][-1]['id']}/extractions", headers=OWNER)
    listing = client.get(f"{base}/suggestions", headers=OWNER).json()
    kinds = [item["content"]["kind"] for item in listing["suggestions"]]
    assert kinds.count("landscape_domain") == 4 and kinds.count("placement") == 6

    accepted = client.post(
        f"{base}/suggestions/acceptance",
        json={"expected_revision": listing["release_revision"]},
        headers=OWNER,
    ).json()

    release = accepted["release"]
    assert {item["id"] for item in release["landscape_domains"]} == {
        "ordering",
        "fulfilment",
        "ordering-un-assisted",
        "ordering-data-case",
    }
    systems = {item["id"]: item for item in release["systems"]}
    assert systems["order-portal"]["landscape_domain_id"] == "ordering-un-assisted"
    assert systems["notifier"]["description"] == "Template-driven SMS and email notifications."
    decided = client.get(f"{base}/suggestions", headers=OWNER).json()["suggestions"]
    waiting = [
        item for item in decided if item["content"]["kind"] in {"landscape_domain", "placement"}
    ]
    assert {item["status"] for item in waiting} == {CandidateStatus.ACCEPTED.value}
