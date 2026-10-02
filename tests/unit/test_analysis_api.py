"""Tests for analysis API endpoints.

Uses the shared `client` fixture, whose container is backed by the
deterministic FakeRequirementAnalyzer.
"""

from fastapi.testclient import TestClient

from tests.unit.workflow_helpers import post_analysis, screen_current_knowledge


def test_analyze_requirement_api(client: TestClient) -> None:
    # Create requirement first
    resp = client.post("/requirements", json={"title": "T", "description": "D"})
    assert resp.status_code == 201
    req_id = resp.json()["id"]

    # Analyze
    analyze_resp = post_analysis(client, req_id)
    assert analyze_resp.status_code == 200
    data = analyze_resp.json()
    assert data["requirement_id"] == req_id
    assert len(data["known_facts"]) == 1
    assert data["known_facts"][0]["statement"] == "This is a known fact."
    assert data["clarifications"] == []
    assert data["human_confirmed"] is False
    assert data["confirmed_at"] is None

    # Get Analysis
    get_resp = client.get(f"/requirements/{req_id}/analysis")
    assert get_resp.status_code == 200
    assert get_resp.json() == data


def test_answer_analysis_item_and_reanalyze_same_requirement(client: TestClient) -> None:
    created = client.post("/requirements", json={"title": "T", "description": "D"})
    req_id = created.json()["id"]
    analysis = post_analysis(client, req_id).json()

    response = client.post(
        f"/requirements/{req_id}/analysis/clarifications",
        json={
            "answers": [
                {
                    "kind": "open_question",
                    "subject": "Is this a question?",
                    "answer": "The Product team owns it.",
                }
            ],
            "expected_analysis_version": analysis["version"],
        },
    )

    assert response.status_code == 200
    data = response.json()
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
    analysis = post_analysis(client, req_id).json()

    response = client.post(
        f"/requirements/{req_id}/analysis/clarifications",
        json={
            "answers": [{"kind": "ambiguity", "subject": "Old item", "answer": "Answer"}],
            "expected_analysis_version": analysis["version"],
        },
    )

    assert response.status_code == 409


def test_confirmation_rejects_a_stale_analysis_version(client: TestClient) -> None:
    created = client.post("/requirements", json={"title": "T", "description": "D"})
    requirement_id = created.json()["id"]
    original = post_analysis(client, requirement_id).json()
    changed = client.post(
        f"/requirements/{requirement_id}/analysis/clarifications",
        json={
            "answers": [
                {
                    "kind": "open_question",
                    "subject": "Is this a question?",
                    "answer": "The owner answered after the page loaded.",
                }
            ],
            "expected_analysis_version": original["version"],
        },
    )
    assert changed.status_code == 200

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
    analysis = post_analysis(client, req_id).json()

    blocked = client.post(
        f"/requirements/{req_id}/analysis/confirmation",
        json={"expected_version": analysis["version"]},
    )
    assert blocked.status_code == 409

    clarified = client.post(
        f"/requirements/{req_id}/analysis/clarifications",
        json={
            "answers": [
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
            "expected_analysis_version": analysis["version"],
        },
    )
    assert clarified.status_code == 200
    assert clarified.json()["human_confirmed"] is False

    proposal = clarified.json()["business_intent"]["proposals"][0]
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

    reanalyzed = post_analysis(client, req_id, force=True)
    assert reanalyzed.status_code == 200
    assert reanalyzed.json()["human_confirmed"] is False


def test_owner_reviews_intent_proposal_with_audited_optimistic_decisions(
    client: TestClient,
) -> None:
    requirement_id = client.post(
        "/requirements", json={"title": "Need", "description": "Customers need self-service"}
    ).json()["id"]
    analysis = post_analysis(client, requirement_id).json()
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
    first = post_analysis(client, requirement_id).json()
    proposal = first["business_intent"]["proposals"][0]
    client.patch(
        f"/requirements/{requirement_id}/analysis/proposals/{proposal['id']}",
        json={"decision": "accepted", "expected_version": 1},
    )

    second = post_analysis(client, requirement_id, force=True)
    assert second.status_code == 200
    carried = second.json()["business_intent"]["proposals"][0]
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
    replacement = post_analysis(client, requirement_id).json()
    new_proposal = replacement["business_intent"]["proposals"][0]
    assert new_proposal["id"] != proposal["id"]
    assert new_proposal["status"] == "pending"


def test_analyze_unknown_requirement(client: TestClient) -> None:
    resp = client.post("/requirements/unknown/analysis", json={"context_token": "unknown-context"})
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
    post_analysis(client, req_id)
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
