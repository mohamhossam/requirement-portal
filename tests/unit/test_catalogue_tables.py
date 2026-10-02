"""Catalogue tables are read from their cells, exactly and the same way every time (ADR-0093).

The reported failure: a 39-system landscape was left to a model whose answers
sampled a different 9 to 45 suggestions each time, and whose integration links
joined activities to the wrong systems.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.ports.catalogue_extractor import (
    CatalogueAnswerUnusableError,
    CatalogueProposal,
    ExtractionRequest,
    ExtractionSegment,
    KnownSystem,
    ProposedChange,
)
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateBasis,
    CandidateContent,
    CandidateKind,
)
from smb_requirement_agent.domain.architecture.knowledge import RelationshipKind
from smb_requirement_agent.infrastructure.architecture.catalogue_tables import (
    READER,
    READER_VERSION,
    CatalogueTableReader,
    TableFirstCatalogueExtractor,
)
from smb_requirement_agent.infrastructure.architecture.markdown_passages import markdown_passages
from smb_requirement_agent.infrastructure.llm.prompts.catalogue_extraction_prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "catalogue" / "synthetic_landscape.md"
OWNER = {"X-Fake-Actor-Id": "fake-owner"}


def _request(text: str, *known: KnownSystem) -> ExtractionRequest:
    segments = tuple(
        ExtractionSegment(
            number, item.location, item.text, section=item.heading_path, cells=item.cells
        )
        for number, item in enumerate(markdown_passages(text), 1)
    )
    return ExtractionRequest("Landscape", segments, known)


def _links(changes: list[ProposedChange]) -> list[tuple[str, str, str]]:
    return [
        (item.content.system_id, item.content.target_system_id or "", item.content.text)
        for item in changes
        if item.content.kind is CandidateKind.RELATIONSHIP
    ]


def test_a_landscape_reads_into_its_systems_and_their_integrations() -> None:
    request = _request(FIXTURE.read_text(encoding="utf-8"))

    reading = CatalogueTableReader().read(request)

    systems = {
        item.content.system_id: (item.content.name, item.content.aliases)
        for item in reading.changes
        if item.content.kind is CandidateKind.SYSTEM
    }
    assert systems == {
        "order-portal": ("Order Portal", ("SYS-PORTAL",)),
        "order-gateway": ("Order Gateway", ("OGW", "Gateway", "SYS-GATEWAY")),
        "pricing-engine": ("Pricing Engine", ("SYS-PRICING",)),
        "flow-engine": ("Flow Engine", ("SYS-FLOW",)),
        "field-desk": ("Field Desk", ("Field Desk Pro", "SYS-FIELD")),
        "notifier": ("Notifier", ("SYS-NOTIFY",)),
    }
    links = _links(reading.changes)
    assert len(links) == 12
    # "Flow Engine / Order Gateway" names two systems; neither is one system's name.
    assert ("pricing-engine", "flow-engine", "Integrates with Flow Engine") in links
    assert ("pricing-engine", "order-gateway", "Integrates with Order Gateway") in links
    # An integration between two activities links their performing systems, with how.
    (api,) = [item for item in reading.changes if item.content.text == "Basket (API, Order API)"]
    assert (api.content.system_id, api.content.target_system_id) == ("order-portal", "flow-engine")
    assert api.content.relationship_kind is RelationshipKind.CALLS_API
    # Each suggestion cites its own row, verbatim, and says the reader proposed it.
    assert api.locations == ("line 84",) and api.quote.startswith("From: 10 | To: 20")
    assert {item.reader for item in reading.changes} == {(READER, READER_VERSION)}
    # Domain, product-fact, integration and flow-rule rows, a journey's drawn flow and its
    # activities' detail bullets are taken whole; system, component, responsibility and
    # activity rows, and activity descriptions, still go to the model for capabilities.
    assert len(reading.consumed) == 14 and len(reading.read) == 16


def test_reading_the_same_tables_again_gives_the_same_suggestions() -> None:
    request = _request(FIXTURE.read_text(encoding="utf-8"))

    readings = [CatalogueTableReader().read(request).changes for _ in range(3)]

    assert readings[0] == readings[1] == readings[2]


def test_activities_on_one_system_and_gap_rows_link_nothing() -> None:
    reading = CatalogueTableReader().read(_request(FIXTURE.read_text(encoding="utf-8")))

    # 20 → 25 stays inside Flow Engine; 25 → 30 is marked GAP.
    assert not any("Validated order" in text for *_, text in _links(reading.changes))
    assert not any("Installation request" in text for *_, text in _links(reading.changes))


TABLE = (
    "| System | ID | Integrations | Aliases | Evidence |\n"
    "|---|---|---|---|---|\n"
    "| 🎧 Care Desk | SYS-CARE | Billing via TIBCO, WFM / Remedy, "
    "Same service context as the portal | — | CONFIRMED |\n"
    "| 🧭 Route Planner | SYS-ROUTE | ECM | — | INFERRED |\n"
    "| 📦 Stock Keeper | SYS-STOCK | Care Desk | — | GAP |\n"
    "| 🏷️ ECM (catalog) | SYS-ECM | — | Ericsson Catalog Manager | CONFIRMED |\n"
)


def test_entries_keep_their_qualifier_known_names_and_skip_phrases_and_gaps() -> None:
    reading = CatalogueTableReader().read(
        _request(TABLE, KnownSystem("wfm", "WFM / Remedy", ("WFM",)))
    )

    assert _links(reading.changes) == [
        ("care-desk", "billing", "Integrates with Billing via TIBCO"),
        # A known system's name is one system, slash and all.
        ("care-desk", "wfm", "Integrates with WFM / Remedy"),
        # "ECM" is "ECM (catalog)" without its qualifier.
        ("route-planner", "ecm-catalog", "Integrates with ECM"),
    ]
    inferred = [item for item in reading.changes if item.basis is CandidateBasis.INFERRED]
    assert {item.content.system_id for item in inferred} == {"route-planner"}
    assert inferred[0].rationale == "The document marks this row INFERRED."
    assert "stock-keeper" not in {item.content.system_id for item in reading.changes}


# The extractor in front of the model ---------------------------------------------------------


class _Model:
    supports_images = False
    model = "scripted"
    prompt_version = "catalogue-extraction-v7"

    def __init__(self, *changes: ProposedChange, fail: bool = False) -> None:
        self.changes = changes
        self.fail = fail
        self.requests: list[ExtractionRequest] = []

    def propose(self, request: ExtractionRequest) -> CatalogueProposal:
        self.requests.append(request)
        if self.fail:
            raise CatalogueAnswerUnusableError("No part of the document could be read.")
        return CatalogueProposal(self.changes, self.model, self.prompt_version, ("Model note.",))


def _from_model(kind: CandidateKind, location: str, **values: Any) -> ProposedChange:
    return ProposedChange(CandidateContent(kind, "order-portal", **values), (location,), "quoted")


def test_the_model_reads_only_what_the_tables_leave_and_never_repeats_them() -> None:
    capability = _from_model(
        CandidateKind.CAPABILITY,
        "line 22",
        name="Order placement",
        capability_id="order-placement",
        triggers=("place orders",),
    )
    model = _Model(
        capability,
        _from_model(CandidateKind.SYSTEM, "line 22", name="Order Portal"),
        _from_model(
            CandidateKind.RELATIONSHIP, "line 22", target_system_id="x", text="Integrates with X"
        ),
    )
    extractor = TableFirstCatalogueExtractor(model, CatalogueTableReader())

    proposal = extractor.propose(_request(FIXTURE.read_text(encoding="utf-8")))

    (sent,) = model.requests
    assert not any(item.text.startswith("From: ") for item in sent.segments)
    assert [item.location for item in sent.segments if item.read][:1] == ["line 22"]
    # From a row already read, only the capability is kept from the model.
    from_model = [item for item in proposal.changes if item.reader is None]
    assert from_model == [capability]
    assert proposal.prompt_version == f"catalogue-extraction-v7+{READER_VERSION}"
    assert proposal.warnings == (
        "Model note.",
        "30 table row(s) were read directly, without the model.",
    )


def test_a_model_failure_keeps_what_the_tables_gave() -> None:
    extractor = TableFirstCatalogueExtractor(_Model(fail=True), CatalogueTableReader())

    proposal = extractor.propose(_request(FIXTURE.read_text(encoding="utf-8")))

    assert len(proposal.changes) == 30
    assert "The model could not read the rest of the document." in proposal.warnings[-1]
    with pytest.raises(CatalogueAnswerUnusableError):
        extractor.propose(_request("Prose about nothing in particular.\n"))


def test_a_row_already_read_is_marked_so_in_the_prompt() -> None:
    segment = ExtractionSegment(1, "line 4", "System: Order Portal", read=True)

    sent = json.loads(build_user_prompt(ExtractionRequest("Doc", (segment,), ())))

    assert sent["segments"][0]["read"] is True
    assert (
        '"read": true' in SYSTEM_PROMPT
        and "propose only capabilities and constraints" in SYSTEM_PROMPT
    )


def test_suggestions_read_from_tables_say_so_through_the_api(client: TestClient) -> None:
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

    systems = [item for item in listing["suggestions"] if item["content"]["kind"] == "system"]
    assert {item["content"]["name"] for item in systems} >= {"Order Portal", "Notifier"}
    assert {item["model"] for item in systems} == {READER}
    assert any(
        "read directly, without the model" in note for note in listing["runs"][0]["warnings"]
    )


def test_rows_without_cells_are_left_to_the_model() -> None:
    plain = ExtractionSegment(1, "row 2", "R2C1: Order Hub | R2C2: Sales")

    reading = CatalogueTableReader().read(ExtractionRequest("Sheet", (plain,), ()))

    assert reading.changes == [] and not reading.read and not reading.consumed
    assert replace(plain, read=True).read
