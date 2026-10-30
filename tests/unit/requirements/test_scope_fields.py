"""The scope statement a standard BRD carries: current state, proposed state, out of scope."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.requirements.domain.requirement.entities import RequirementDraft
from smb_requirement_agent.requirements.domain.requirement.errors import (
    RequirementIntakeTooLargeError,
)
from smb_requirement_agent.requirements.domain.requirement.intake_limits import (
    MAX_CONTEXT_CHARACTERS,
    MAX_LIST_ITEMS,
    require_within_intake_limits,
)
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementVersion,
)
from smb_requirement_agent.requirements.infrastructure.requirement_snapshot import (
    requirement_draft_from_payload,
    requirement_draft_to_payload,
    requirement_from_payload,
    requirement_to_payload,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.unit.workflow_helpers import confirm_fake_analysis, post_analysis

SCOPE = {
    "current_state": "Orders are keyed by hand in the shop.",
    "proposed_state": "Customers order online and the order provisions itself.",
    "out_of_scope": ["Enterprise accounts", "Hardware resale"],
}


def test_intake_limits_cover_the_scope_fields() -> None:
    with pytest.raises(RequirementIntakeTooLargeError, match="current_state"):
        require_within_intake_limits(
            title="t",
            description="d",
            desired_outcome=None,
            customer_context=None,
            lists={},
            current_state="x" * (MAX_CONTEXT_CHARACTERS + 1),
        )
    with pytest.raises(RequirementIntakeTooLargeError, match="proposed_state"):
        require_within_intake_limits(
            title="t",
            description="d",
            desired_outcome=None,
            customer_context=None,
            lists={},
            proposed_state="x" * (MAX_CONTEXT_CHARACTERS + 1),
        )
    with pytest.raises(RequirementIntakeTooLargeError, match="out_of_scope"):
        require_within_intake_limits(
            title="t",
            description="d",
            desired_outcome=None,
            customer_context=None,
            lists={"out_of_scope": ["x"] * (MAX_LIST_ITEMS + 1)},
        )


def test_draft_keeps_positional_construction_and_strips_the_scope_fields() -> None:
    draft = RequirementDraft(
        RequirementId("d-1"),
        "Title",
        "Need",
        "",
        "",
        (),
        (),
        (),
        (),
        RequirementVersion(1),
        datetime(2026, 1, 1, tzinfo=UTC),
        current_state="  today  ",
        out_of_scope=(" a ", "", "b"),
    )

    assert draft.current_state == "today"
    assert draft.proposed_state == ""
    assert draft.out_of_scope == ("a", "b")
    round_tripped = requirement_draft_from_payload(requirement_draft_to_payload(draft))
    assert round_tripped == draft
    # A payload written before the fields existed still reads.
    legacy = {
        key: value
        for key, value in requirement_draft_to_payload(draft).items()
        if key not in ("current_state", "proposed_state", "out_of_scope")
    }
    assert requirement_draft_from_payload(legacy).out_of_scope == ()


def test_requirement_payload_omits_empty_scope_fields_and_reads_legacy_rows(
    client: TestClient, container: Container
) -> None:
    plain = client.post("/requirements", json={"title": "Plain", "description": "No scope."}).json()
    scoped = client.post(
        "/requirements", json={"title": "Scoped", "description": "With scope.", **SCOPE}
    ).json()
    repository = container.requirement_repository
    plain_entity = repository.get(RequirementId(plain["id"]))
    scoped_entity = repository.get(RequirementId(scoped["id"]))
    assert plain_entity is not None and scoped_entity is not None

    plain_payload = requirement_to_payload(plain_entity)
    scoped_payload = requirement_to_payload(scoped_entity)

    assert not {"current_state", "proposed_state", "out_of_scope"} & plain_payload.keys()
    assert scoped_payload["out_of_scope"] == SCOPE["out_of_scope"]
    assert requirement_from_payload(scoped_payload) == scoped_entity
    assert requirement_from_payload(plain_payload) == plain_entity


def test_scope_fields_are_captured_edited_and_echoed(client: TestClient) -> None:
    created = client.post(
        "/requirements", json={"title": "Scoped", "description": "With scope.", **SCOPE}
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["current_state"] == SCOPE["current_state"]
    assert body["proposed_state"] == SCOPE["proposed_state"]
    assert body["out_of_scope"] == SCOPE["out_of_scope"]
    requirement_id = body["id"]

    # An edit to only an out-of-scope line is a real change: saved, versioned, revised.
    edited = client.put(
        f"/requirements/{requirement_id}",
        json={
            "title": "Scoped",
            "description": "With scope.",
            "out_of_scope": ["Enterprise accounts"],
            "expected_version": body["version"],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["version"] == body["version"] + 1
    assert edited.json()["out_of_scope"] == ["Enterprise accounts"]
    # Fields left out of the request keep their value.
    assert edited.json()["current_state"] == SCOPE["current_state"]

    history = client.get(f"/requirements/{requirement_id}/revisions").json()
    needs = history["requirement_revisions"]
    assert needs[-1]["out_of_scope"] == ["Enterprise accounts"]
    assert needs[-1]["current_state"] == SCOPE["current_state"]
    assert needs[0]["out_of_scope"] == SCOPE["out_of_scope"]


def test_editing_only_scope_fields_discards_the_analysis_like_any_source_edit(
    client: TestClient,
) -> None:
    requirement_id = client.post(
        "/requirements", json={"title": "Scoped", "description": "With scope."}
    ).json()["id"]
    assert post_analysis(client, requirement_id).succeeded
    current = client.get(f"/requirements/{requirement_id}").json()

    preview = client.post(
        f"/requirements/{requirement_id}/impact-preview",
        json={
            "title": current["title"],
            "description": current["description"],
            "proposed_state": "Self-service ordering.",
            "expected_version": current["version"],
        },
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["source_changed"] is True

    refused = client.put(
        f"/requirements/{requirement_id}",
        json={
            "title": current["title"],
            "description": current["description"],
            "proposed_state": "Self-service ordering.",
            "expected_version": current["version"],
        },
    )
    assert refused.status_code == 409
    accepted = client.put(
        f"/requirements/{requirement_id}",
        json={
            "title": current["title"],
            "description": current["description"],
            "proposed_state": "Self-service ordering.",
            "expected_version": current["version"],
            "impact_acknowledged": True,
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert client.get(f"/requirements/{requirement_id}/analysis").status_code == 404


def test_drafts_carry_the_scope_fields_into_the_requirement(client: TestClient) -> None:
    draft = client.post("/requirements/drafts", json={"title": "Draft", **SCOPE}).json()
    assert draft["out_of_scope"] == SCOPE["out_of_scope"]
    saved = client.put(
        f"/requirements/drafts/{draft['id']}",
        json={
            "title": "Draft",
            "description": "Now with a need.",
            **SCOPE,
            "expected_version": draft["version"],
        },
    )
    assert saved.status_code == 200, saved.text
    promoted = client.post(
        f"/requirements/drafts/{draft['id']}/promote",
        json={"expected_version": saved.json()["version"]},
    )
    assert promoted.status_code in (200, 201), promoted.text
    assert promoted.json()["current_state"] == SCOPE["current_state"]
    assert promoted.json()["out_of_scope"] == SCOPE["out_of_scope"]


def test_document_scope_section_carries_the_statement(client: TestClient) -> None:
    requirement_id = client.post(
        "/requirements", json={"title": "Scoped", "description": "With scope.", **SCOPE}
    ).json()["id"]
    assert post_analysis(client, requirement_id).succeeded
    confirm_fake_analysis(client, requirement_id)
    history = client.get(f"/requirements/{requirement_id}/revisions").json()
    revision = next(
        item["number"]
        for item in reversed(history["breakdown_revisions"])
        if item["specification_available"]
    )

    markdown = client.get(
        f"/requirements/{requirement_id}/revisions/{revision}/specification?format=md"
    ).text

    assert "### In scope" in markdown
    assert "### Out of scope\n\n- Enterprise accounts\n- Hardware resale" in markdown
    assert f"### Current state\n\n{SCOPE['current_state']}" in markdown
    assert f"### Proposed state\n\n{SCOPE['proposed_state']}" in markdown
