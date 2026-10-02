"""Documents become catalogue suggestions with citations; only maintainers apply them."""

from __future__ import annotations

import io
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from smb_requirement_agent.application.ports.catalogue_extractor import (
    CatalogueExtractionError,
    ExtractionRequest,
    ExtractionSegment,
    KnownSystem,
)
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateContent,
    CandidateDependencyError,
    CandidateKind,
    CandidateMatch,
    apply_candidate,
    classify,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    KnowledgeCapability,
    SystemDefinition,
)
from smb_requirement_agent.infrastructure.llm.catalogue_extraction import (
    ChangeOutput,
    ExtractionOutput,
    StructuredCatalogueExtractor,
)

OWNER = {"X-Fake-Actor-Id": "fake-owner"}
READER = {"X-Fake-Actor-Id": "fake-reviewer"}
DRAFT = ArchitectureKnowledge(
    "draft",
    1,
    (
        SystemDefinition(
            "bcrm",
            "BCRM",
            aliases=("customer records",),
            capabilities=(KnowledgeCapability("lookup", "Lookup", ("find customer",)),),
        ),
    ),
    (),
)


def test_classify_and_apply_merge_without_losing_existing_information() -> None:
    known_alias = CandidateContent(CandidateKind.SYSTEM, "crm", name="customer records")
    new_alias = CandidateContent(CandidateKind.SYSTEM, "bcrm", name="BCRM", aliases=("CRM",))
    capability = CandidateContent(
        CandidateKind.CAPABILITY,
        "customer records",
        name="Lookup",
        capability_id="lookup",
        triggers=("search account",),
    )
    orphan = CandidateContent(CandidateKind.CONSTRAINT, "billing", text="Nightly batch only")
    relationship = CandidateContent(
        CandidateKind.RELATIONSHIP, "billing", target_system_id="bcrm", text="Reads customers"
    )

    assert classify(known_alias, DRAFT) is CandidateMatch.ALREADY_PRESENT
    assert classify(new_alias, DRAFT) is CandidateMatch.UPDATES_EXISTING
    assert classify(capability, DRAFT) is CandidateMatch.UPDATES_EXISTING
    assert classify(orphan, DRAFT) is CandidateMatch.NEEDS_SYSTEM
    assert classify(relationship, DRAFT) is CandidateMatch.NEEDS_SYSTEM

    merged = apply_candidate(capability, apply_candidate(new_alias, DRAFT))
    system = merged.systems[0]
    assert system.aliases == ("customer records", "CRM")
    assert system.capabilities[0].triggers == ("find customer", "search account")
    with pytest.raises(CandidateDependencyError, match="billing"):
        apply_candidate(orphan, merged)
    with_billing = apply_candidate(
        CandidateContent(CandidateKind.SYSTEM, "billing", name="Billing"), merged
    )
    linked = apply_candidate(relationship, with_billing)
    assert linked.relationships[0].source_system_id == "billing"
    assert classify(relationship, linked) is CandidateMatch.ALREADY_PRESENT


class _Client:
    model = "test-model"

    def __init__(self, output: ExtractionOutput) -> None:
        self.output = output
        self.images: Sequence[tuple[str, bytes]] = ()

    def parse(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_type: type[Any],
        images: Sequence[tuple[str, bytes]] = (),
    ) -> Any:
        self.images = images
        return self.output


def _change(**values: Any) -> ChangeOutput:
    defaults: dict[str, Any] = {
        "kind": "system",
        "system": "Order Hub",
        "name": "Order Hub",
        "name_ar": None,
        "aliases": [],
        "triggers": [],
        "target_system": None,
        "component": None,
        "technology": None,
        "domain": None,
        "parent_domain": None,
        "offering": None,
        "journey": None,
        "text": None,
        "evidence_numbers": [1],
        "quote": "Order Hub captures orders",
        "basis": "stated",
        "reasoning": None,
        "relationship_kind": None,
    }
    return ChangeOutput(**(defaults | values))


REQUEST = ExtractionRequest(
    "Architecture",
    (
        ExtractionSegment(1, "paragraph 1", "The Order Hub captures orders from partners."),
        ExtractionSegment(2, "paragraph 2", "Order Hub calls the customer records system."),
    ),
    (KnownSystem("bcrm", "BCRM", ("customer records",)),),
)


def test_adapter_resolves_system_names_and_drops_unverifiable_citations() -> None:
    client = _Client(
        ExtractionOutput(
            changes=[
                _change(),
                _change(
                    kind="relationship",
                    system="Order Hub",
                    name=None,
                    target_system="customer records",
                    text="Reads customers",
                    evidence_numbers=[2],
                    quote="calls the customer records system",
                ),
                _change(kind="constraint", text="Invented", evidence_numbers=[9], quote="x"),
                _change(name="Other", system="Other", quote="not in the document"),
            ]
        )
    )

    proposal = StructuredCatalogueExtractor(client, supports_images=False).propose(REQUEST)

    assert [item.content.kind for item in proposal.changes] == [
        CandidateKind.SYSTEM,
        CandidateKind.RELATIONSHIP,
    ]
    assert proposal.changes[0].content.system_id == "order-hub"
    assert proposal.changes[1].content.system_id == "order-hub"
    assert proposal.changes[1].content.target_system_id == "bcrm"
    assert proposal.warnings == (
        "2 suggestion(s) were left out because their citation could not be checked.",
    )
    assert proposal.model == "test-model"


def test_adapter_fails_when_nothing_is_verifiable_and_accepts_image_readings() -> None:
    bad = _Client(ExtractionOutput(changes=[_change(quote="made up")]))
    with pytest.raises(CatalogueExtractionError):
        StructuredCatalogueExtractor(bad, supports_images=True).propose(REQUEST)

    image_client = _Client(ExtractionOutput(changes=[_change(quote="ORDER HUB")]))
    image_request = ExtractionRequest(
        "Diagram", (ExtractionSegment(1, "image", image_mime_type="image/png", image=b"png"),), ()
    )
    proposal = StructuredCatalogueExtractor(image_client, supports_images=True).propose(
        image_request
    )
    assert proposal.changes[0].content.name == "Order Hub"
    assert image_client.images == (("image/png", b"png"),)
    empty = StructuredCatalogueExtractor(
        _Client(ExtractionOutput(changes=[])), supports_images=True
    )
    assert empty.propose(REQUEST).changes == ()


SOURCE = b"""System: Order Hub
Capability: Order capture (capture order, new order)
Constraint: Read-only between midnight and 2am
Order Hub depends on BCRM for customer lookup
"""


def _upload(client: TestClient, release: dict[str, Any], name: str, body: bytes, mime: str) -> Any:
    response = client.post(
        f"/architecture-knowledge/releases/{release['id']}/documents",
        data={
            "title": "Order Hub design",
            "language": "en",
            "expected_revision": release["revision"],
        },
        files={"file": (name, body, mime)},
        headers=OWNER,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_extraction_to_accepted_draft_through_the_api(client: TestClient) -> None:
    draft = client.post(
        "/architecture-knowledge/releases", json={"name": "Next version"}, headers=OWNER
    ).json()
    draft = _upload(client, draft, "design.txt", SOURCE, "text/plain")
    base = f"/architecture-knowledge/releases/{draft['id']}"
    version_id = draft["documents"][-1]["id"]

    job = client.post(f"{base}/documents/{version_id}/extractions", headers=OWNER)
    again = client.post(f"{base}/documents/{version_id}/extractions", headers=OWNER)
    assert job.status_code == 202
    assert job.json()["status"] == "succeeded"
    assert again.json()["id"] == job.json()["id"]
    assert (
        client.post(f"{base}/documents/{version_id}/extractions", headers=READER).status_code == 403
    )

    listing = client.get(f"{base}/suggestions", headers=OWNER).json()
    by_kind = {item["content"]["kind"]: item for item in listing["suggestions"]}
    assert set(by_kind) == {"system", "capability", "constraint", "relationship"}
    assert by_kind["capability"]["match"] == "needs_system"
    assert by_kind["system"]["citations"][0]["location"] == "lines 1-4"
    assert listing["runs"][0]["candidate_count"] == 4

    early = client.post(
        f"{base}/suggestions/{by_kind['capability']['id']}/decision",
        json={"expected_revision": listing["release_revision"], "accept": True},
        headers=OWNER,
    )
    assert early.status_code == 409
    edited_system = by_kind["system"]["content"] | {"aliases": ["OH"]}
    accepted = client.post(
        f"{base}/suggestions/{by_kind['system']['id']}/decision",
        json={
            "expected_revision": listing["release_revision"],
            "accept": True,
            "content": edited_system,
        },
        headers=OWNER,
    )
    assert accepted.status_code == 200, accepted.text
    rejected = client.post(
        f"{base}/suggestions/{by_kind['constraint']['id']}/decision",
        json={"expected_revision": accepted.json()["revision"], "accept": False},
        headers=OWNER,
    )
    assert rejected.status_code == 200
    rest = client.post(
        f"{base}/suggestions/acceptance",
        json={"expected_revision": accepted.json()["revision"]},
        headers=OWNER,
    ).json()

    assert rest["remaining"] == 0
    order_hub = next(item for item in rest["release"]["systems"] if item["id"] == "order-hub")
    assert order_hub["aliases"] == ["OH"]
    assert order_hub["capabilities"][0]["triggers"] == ["capture order", "new order"]
    assert order_hub["constraints"] == []
    assert {
        "source_system_id": "order-hub",
        "target_system_id": "bcrm",
        "description": "customer lookup",
        "kind": "unspecified",
    } in rest["release"]["relationships"]
    decided = client.get(f"{base}/suggestions", headers=OWNER).json()["suggestions"]
    assert {item["status"] for item in decided} == {"accepted", "rejected"}
    assert next(item for item in decided if item["content"]["kind"] == "system")["edited"]
    again_decided = client.post(
        f"{base}/suggestions/{by_kind['system']['id']}/decision",
        json={"expected_revision": rest["release"]["revision"], "accept": False},
        headers=OWNER,
    )
    assert again_decided.status_code == 409


def test_a_dependency_of_a_system_on_itself_is_left_out_with_a_note(client: TestClient) -> None:
    """Integration rows between two steps of one system read as RTF → RTF; accepting failed."""
    draft = client.post(
        "/architecture-knowledge/releases", json={"name": "Next version"}, headers=OWNER
    ).json()
    body = b"System: Order Hub\nOrder Hub depends on order hub for validation\n"
    draft = _upload(client, draft, "design.txt", body, "text/plain")
    base = f"/architecture-knowledge/releases/{draft['id']}"
    client.post(f"{base}/documents/{draft['documents'][-1]['id']}/extractions", headers=OWNER)

    listing = client.get(f"{base}/suggestions", headers=OWNER).json()

    assert [item["content"]["kind"] for item in listing["suggestions"]] == ["system"]
    assert (
        "1 dependency suggestion(s) were left out because they linked a system to itself."
        in listing["runs"][0]["warnings"]
    )


def test_images_are_accepted_as_sources_and_read_for_suggestions(client: TestClient) -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buffer, format="PNG")
    draft = client.post(
        "/architecture-knowledge/releases", json={"name": "Next version"}, headers=OWNER
    ).json()
    draft = _upload(client, draft, "diagram.png", buffer.getvalue(), "image/png")
    base = f"/architecture-knowledge/releases/{draft['id']}"

    job = client.post(
        f"{base}/documents/{draft['documents'][-1]['id']}/extractions", headers=OWNER
    ).json()

    assert job["status"] == "succeeded"
    suggestions = client.get(f"{base}/suggestions", headers=OWNER).json()["suggestions"]
    assert suggestions[0]["content"]["name"] == "Order Hub design"
    assert suggestions[0]["citations"][0]["location"] == "image"
    build = client.post(
        f"{base}/build", json={"expected_revision": draft["revision"]}, headers=OWNER
    )
    assert build.json()["status"] == "succeeded"
