"""API tests: responses report allowed actions, and a blocked action's reason is the refusal."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.unit.workflow_helpers import (
    confirm_fake_analysis,
    generate_story_tree,
    post_analysis,
    post_epic,
    post_epic_approval,
    post_feature_approval,
    post_features,
    post_stories,
)

ALLOWED = {"allowed": True, "reason": None, "confirmation": None}


def _requirement(client: TestClient) -> str:
    created = client.post("/requirements", json={"title": "T", "description": "D"})
    requirement_id: str = created.json()["id"]
    assert post_analysis(client, requirement_id).status_code == 200
    return requirement_id


def _epic(client: TestClient, requirement_id: str) -> dict[str, Any]:
    body: dict[str, Any] = client.get(f"/requirements/{requirement_id}/epic").json()
    return body


def _feature(client: TestClient, requirement_id: str) -> dict[str, Any]:
    body: dict[str, Any] = client.get(f"/requirements/{requirement_id}/features").json()
    feature: dict[str, Any] = body["features"][0]
    return feature


def test_analysis_reports_whether_an_epic_can_be_generated(client: TestClient) -> None:
    requirement_id = _requirement(client)
    unconfirmed = client.get(f"/requirements/{requirement_id}/analysis").json()

    blocked = unconfirmed["actions"]["generate_epic"]
    assert blocked["allowed"] is False
    refusal = post_epic(client, requirement_id)
    assert refusal.status_code == 409
    assert refusal.json()["message"] == blocked["reason"]

    confirm_fake_analysis(client, requirement_id)
    confirmed = client.get(f"/requirements/{requirement_id}/analysis").json()
    assert confirmed["actions"]["generate_epic"] == ALLOWED


def test_epic_actions_follow_its_review_state(client: TestClient) -> None:
    requirement_id = _requirement(client)
    confirm_fake_analysis(client, requirement_id)
    post_epic(client, requirement_id)

    generated = _epic(client, requirement_id)["actions"]
    assert generated["approve"] == ALLOWED
    assert generated["regenerate"] == ALLOWED
    assert generated["generate_features"]["allowed"] is False
    refusal = post_features(client, requirement_id)
    assert refusal.status_code == 409
    assert refusal.json()["message"] == generated["generate_features"]["reason"]

    assert post_epic_approval(client, requirement_id).status_code == 200
    approved = _epic(client, requirement_id)["actions"]
    assert approved["approve"]["allowed"] is False
    assert approved["generate_features"] == ALLOWED
    assert approved["regenerate"]["allowed"] is True
    assert "has been approved" in approved["regenerate"]["confirmation"]


def test_feature_actions_gate_story_generation(client: TestClient) -> None:
    requirement_id = _requirement(client)
    confirm_fake_analysis(client, requirement_id)
    post_epic(client, requirement_id)
    post_epic_approval(client, requirement_id)
    post_features(client, requirement_id)

    feature = _feature(client, requirement_id)
    blocked = feature["actions"]["generate_stories"]
    assert feature["actions"]["approve"] == ALLOWED
    assert blocked["allowed"] is False
    refusal = post_stories(client, requirement_id, feature["id"])
    assert refusal.status_code == 409
    assert refusal.json()["message"] == blocked["reason"]

    assert post_feature_approval(client, requirement_id, feature["id"]).status_code == 200
    assert _feature(client, requirement_id)["actions"]["generate_stories"] == ALLOWED


def test_generated_stories_report_their_actions(client: TestClient) -> None:
    _, _, stories = generate_story_tree(client)

    assert stories[0]["actions"] == {"approve": ALLOWED, "regenerate": ALLOWED}
