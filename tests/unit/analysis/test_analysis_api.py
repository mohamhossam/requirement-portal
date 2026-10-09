"""Tests for analysis API endpoints.

Uses the shared `client` fixture, whose container is backed by the
deterministic FakeRequirementAnalyzer.
"""

from typing import Any

from fastapi.testclient import TestClient

from tests.job_driver import JobRun, run_job, start_job
from tests.unit.workflow_helpers import post_analysis, screen_current_knowledge


def _analyse(client: TestClient, requirement_id: str, *, force: bool = False) -> dict[str, Any]:
    run = post_analysis(client, requirement_id, force=force)
    assert run.succeeded, run.job
    response = client.get(f"/requirements/{requirement_id}/analysis")
    assert response.status_code == 200
    return dict(response.json())


def _clarify(
    client: TestClient, requirement_id: str, answers: list[dict[str, str]], version: int
) -> JobRun:
    return run_job(
        client,
        requirement_id,
        "clarify_requirement_analysis",
        answers=answers,
        expected_analysis_version=version,
    )


def test_analyze_requirement_api(client: TestClient) -> None:
    # Create requirement first
    resp = client.post("/requirements", json={"title": "T", "description": "D"})
    assert resp.status_code == 201
    req_id = resp.json()["id"]

    # Analyze
    data = _analyse(client, req_id)
    assert data["requirement_id"] == req_id
    assert len(data["known_facts"]) == 1
    assert data["known_facts"][0]["statement"] == "This is a known fact."
    assert data["clarifications"] == []
    assert data["human_confirmed"] is False
    assert data["confirmed_at"] is None


def test_answer_analysis_item_and_reanalyze_same_requirement(client: TestClient) -> None:
    created = client.post("/requirements", json={"title": "T", "description": "D"})
    req_id = created.json()["id"]
    analysis = _analyse(client, req_id)

    clarified = _clarify(
        client,
        req_id,
        [
            {
                "kind": "open_question",
                "subject": "Is this a question?",
                "answer": "The Product team owns it.",
            }
        ],
        analysis["version"],
    )

    assert clarified.succeeded, clarified.job
    data = client.get(f"/requirements/{req_id}/analysis").json()
    assert data["open_questions"] == []
    clarification = data["clarifications"][0]
    assert clarification["kind"] == "open_question"
    assert clarification["subject"] == "Is this a question?"
    assert clarification["answer"] == "The Product team owns it."
    assert clarification["question_id"]
    assert clarification["answered_by"]["id"] == "fake-owner"
    assert clarification["answered_at"]


def test_answer_rejects_stale_analysis_item(client: TestClient) -> None:
    created = client.post("/requirements", json={"title": "T", "description": "D"})
    req_id = created.json()["id"]
    analysis = _analyse(client, req_id)

    stale = _clarify(
        client,
        req_id,
        [{"kind": "ambiguity", "subject": "Old item", "answer": "Answer"}],
        analysis["version"],
    )

    assert stale.failure is not None
    assert stale.failure["code"] == "analysis_clarification_conflict"


def test_confirmation_rejects_a_stale_analysis_version(client: TestClient) -> None:
    created = client.post("/requirements", json={"title": "T", "description": "D"})
    requirement_id = created.json()["id"]
    original = _analyse(client, requirement_id)
    changed = _clarify(
        client,
        requirement_id,
        [
            {
                "kind": "open_question",
                "subject": "Is this a question?",
                "answer": "The owner answered after the page loaded.",
            }
        ],
        original["version"],
    )
    assert changed.succeeded, changed.job

    stale = client.post(
        f"/requirements/{requirement_id}/analysis/confirmation",
        json={"expected_version": original["version"]},
    )

    assert stale.status_code == 409


def test_answer_loop_can_be_explicitly_confirmed_only_when_resolved(
    client: TestClient,
) -> None:
    created = client.post("/requirements", json={"title": "T", "description": "D"})
    req_id = created.json()["id"]
    analysis = _analyse(client, req_id)

    blocked = client.post(
        f"/requirements/{req_id}/analysis/confirmation",
        json={"expected_version": analysis["version"]},
    )
    assert blocked.status_code == 409

    clarified = _clarify(
        client,
        req_id,
        [
            {
                "kind": "assumption",
                "subject": "This is an assumption.",
                "answer": "Confirmed by the Requirement Owner.",
            },
            {
                "kind": "open_question",
                "subject": "Is this a question?",
                "answer": "Yes.",
            },
            {
                "kind": "ambiguity",
                "subject": "This is ambiguous.",
                "answer": "Use the first interpretation.",
            },
            {
                "kind": "potential_dependency",
                "subject": "This is a dependency.",
                "answer": "The dependency is available.",
            },
        ],
        analysis["version"],
    )
    assert clarified.succeeded, clarified.job
    clarified_analysis = client.get(f"/requirements/{req_id}/analysis").json()
    assert clarified_analysis["human_confirmed"] is False

    proposal = clarified_analysis["business_intent"]["proposals"][0]
    decided = client.patch(
        f"/requirements/{req_id}/analysis/proposals/{proposal['id']}",
        json={"decision": "accepted", "expected_version": proposal["version"]},
    )
    assert decided.status_code == 200

    screen_current_knowledge(client, req_id)
    current = client.get(f"/requirements/{req_id}/analysis").json()
    confirmed = client.post(
        f"/requirements/{req_id}/analysis/confirmation",
        json={"expected_version": current["version"]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["human_confirmed"] is True
    assert confirmed.json()["confirmed_at"] is not None

    reanalyzed = _analyse(client, req_id, force=True)
    assert reanalyzed["human_confirmed"] is False


def test_owner_reviews_intent_proposal_with_audited_optimistic_decisions(
    client: TestClient,
) -> None:
    requirement_id = client.post(
        "/requirements", json={"title": "Need", "description": "Customers need self-service"}
    ).json()["id"]
    analysis = _analyse(client, requirement_id)
    proposal = analysis["business_intent"]["proposals"][0]
    assert proposal["kind"] == "desired_outcome"
    assert proposal["status"] == "pending"

    denied = client.patch(
        f"/requirements/{requirement_id}/analysis/proposals/{proposal['id']}",
        headers={"X-Fake-Actor-Id": "fake-reviewer"},
        json={"decision": "accepted", "expected_version": 1},
    )
    assert denied.status_code == 403

    decided = client.patch(
        f"/requirements/{requirement_id}/analysis/proposals/{proposal['id']}",
        json={
            "decision": "edited",
            "replacement_statement": "Customers complete the journey through self-service.",
            "success_measures": ["Completion can be observed in the channel."],
            "expected_version": 1,
        },
    )
    assert decided.status_code == 200
    reviewed = decided.json()["business_intent"]
    assert reviewed["desired_outcome"]["origin"] == "human_confirmed_ai"
    assert reviewed["proposals"][0]["status"] == "edited"
    assert reviewed["proposals"][0]["decisions"][0]["decided_by"]["id"] == "fake-owner"

    stale = client.patch(
        f"/requirements/{requirement_id}/analysis/proposals/{proposal['id']}",
        json={"decision": "rejected", "expected_version": 1},
    )
    assert stale.status_code == 409


def test_intent_decisions_carry_across_same_source_reanalysis_and_source_edit_invalidates(
    client: TestClient,
) -> None:
    created = client.post(
        "/requirements", json={"title": "Need", "description": "Customers need self-service"}
    ).json()
    requirement_id = created["id"]
    first = _analyse(client, requirement_id)
    proposal = first["business_intent"]["proposals"][0]
    client.patch(
        f"/requirements/{requirement_id}/analysis/proposals/{proposal['id']}",
        json={"decision": "accepted", "expected_version": 1},
    )

    second = _analyse(client, requirement_id, force=True)
    carried = second["business_intent"]["proposals"][0]
    assert carried["id"] == proposal["id"]
    assert carried["status"] == "accepted"

    updated = client.put(
        f"/requirements/{requirement_id}",
        json={
            "title": "Changed need",
            "description": "A materially different customer need",
            "expected_version": created["version"],
            "impact_acknowledged": True,
        },
    )
    assert updated.status_code == 200
    assert client.get(f"/requirements/{requirement_id}/analysis").status_code == 404
    replacement = _analyse(client, requirement_id)
    new_proposal = replacement["business_intent"]["proposals"][0]
    assert new_proposal["id"] != proposal["id"]
    assert new_proposal["status"] == "pending"


def test_analyze_unknown_requirement(client: TestClient) -> None:
    resp = start_job(client, "unknown", "analyse_requirement", context_token="unknown-context")
    assert resp.status_code == 404


def test_get_nonexistent_analysis(client: TestClient) -> None:
    resp = client.post("/requirements", json={"title": "T", "description": "D"})
    req_id = resp.json()["id"]

    get_resp = client.get(f"/requirements/{req_id}/analysis")
    assert get_resp.status_code == 404


def test_update_requirement_invalidates_analysis(client: TestClient) -> None:
    # 1. Create
    resp = client.post("/requirements", json={"title": "T", "description": "D"})
    req_id = resp.json()["id"]

    # 2. Analyze
    assert post_analysis(client, req_id).succeeded
    assert client.get(f"/requirements/{req_id}/analysis").status_code == 200

    # 3. Update
    update_resp = client.put(
        f"/requirements/{req_id}",
        json={
            "title": "T2",
            "description": "D2",
            "expected_version": resp.json()["version"],
            "impact_acknowledged": True,
        },
    )
    assert update_resp.status_code == 200

    # 4. Get Analysis should return 404
    assert client.get(f"/requirements/{req_id}/analysis").status_code == 404
