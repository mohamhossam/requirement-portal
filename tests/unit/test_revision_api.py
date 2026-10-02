"""Revision history API behavior through the offline persistence adapter."""

from fastapi.testclient import TestClient

from tests.unit.workflow_helpers import (
    confirm_fake_analysis,
    post_analysis,
    post_epic,
    post_epic_approval,
    post_feature_approval,
    post_features,
    post_stories,
)


def _requirement(client: TestClient) -> str:
    response = client.post(
        "/requirements", json={"title": "Transfer funds", "description": "Move funds safely."}
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def test_requirement_and_breakdown_history_are_created_automatically(
    client: TestClient,
) -> None:
    requirement_id = _requirement(client)
    assert post_analysis(client, requirement_id).status_code == 200
    confirm_fake_analysis(client, requirement_id)
    assert post_epic(client, requirement_id).status_code == 201

    response = client.get(f"/requirements/{requirement_id}/revisions")

    assert response.status_code == 200
    history = response.json()
    assert len(history["requirement_revisions"]) == 1
    assert len(history["breakdown_revisions"]) >= 2
    assert history["breakdown_revisions"][0]["has_analysis"] is True


def test_breakdown_versions_have_a_deterministic_change_summary(client: TestClient) -> None:
    requirement_id = _requirement(client)
    post_analysis(client, requirement_id)
    confirm_fake_analysis(client, requirement_id)
    post_epic(client, requirement_id)
    history = client.get(f"/requirements/{requirement_id}/revisions").json()
    first = history["breakdown_revisions"][0]["number"]
    last = history["breakdown_revisions"][-1]["number"]

    response = client.get(
        f"/requirements/{requirement_id}/revisions/compare",
        params={"from_revision": first, "to_revision": last},
    )

    assert response.status_code == 200
    assert "Epic content, review state, or staleness changed." in response.json()["changes"]


def test_unknown_revision_returns_404(client: TestClient) -> None:
    requirement_id = _requirement(client)

    response = client.get(
        f"/requirements/{requirement_id}/revisions/compare",
        params={"from_revision": 1, "to_revision": 2},
    )

    assert response.status_code == 404


def test_story_state_is_counted_and_compared_in_breakdown_history(client: TestClient) -> None:
    requirement_id = _requirement(client)
    post_analysis(client, requirement_id)
    confirm_fake_analysis(client, requirement_id)
    post_epic(client, requirement_id)
    post_epic_approval(client, requirement_id)
    features = post_features(client, requirement_id).json()["features"]
    feature_id = features[0]["id"]
    post_feature_approval(client, requirement_id, feature_id)
    before = client.get(f"/requirements/{requirement_id}/revisions").json()["breakdown_revisions"][
        -1
    ]["number"]

    stories = post_stories(client, requirement_id, feature_id).json()["stories"]
    history = client.get(f"/requirements/{requirement_id}/revisions").json()["breakdown_revisions"]
    assert history[-1]["story_count"] == 2
    assert history[-1]["edited_story_count"] == 0
    after_generation = history[-1]["number"]
    comparison = client.get(
        f"/requirements/{requirement_id}/revisions/compare",
        params={"from_revision": before, "to_revision": after_generation},
    ).json()
    assert any(change.startswith("Stories added:") for change in comparison["changes"])

    client.put(
        f"/requirements/{requirement_id}/features/{feature_id}/stories/{stories[0]['id']}",
        json={
            "role": "owner",
            "action": "review a Story",
            "value": "the backlog is accurate",
            "acceptance_criteria": [
                {"given": "a Story", "when": "I review it", "then": "I can edit it"}
            ],
            "expected_version": stories[0]["version"],
        },
    )
    edited_history = client.get(f"/requirements/{requirement_id}/revisions").json()[
        "breakdown_revisions"
    ]
    assert edited_history[-1]["edited_story_count"] == 1
    comparison = client.get(
        f"/requirements/{requirement_id}/revisions/compare",
        params={
            "from_revision": after_generation,
            "to_revision": edited_history[-1]["number"],
        },
    ).json()
    assert any(change.startswith("Stories changed:") for change in comparison["changes"])
