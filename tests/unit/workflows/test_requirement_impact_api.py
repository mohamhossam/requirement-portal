"""Source-change impact preview and acknowledged commit tests."""

from fastapi.testclient import TestClient

from tests.unit.workflow_helpers import post_analysis


def test_change_preview_and_commit_recompute_downstream_impact(client: TestClient) -> None:
    requirement = client.post(
        "/requirements", json={"title": "Title", "description": "Need"}
    ).json()
    requirement_id = requirement["id"]
    assert post_analysis(client, requirement_id).succeeded
    proposed = {
        "title": "Changed",
        "description": "Changed need",
        "expected_version": requirement["version"],
    }

    preview = client.post(f"/requirements/{requirement_id}/impact-preview", json=proposed)

    assert preview.status_code == 200
    assert preview.json() == {
        "requirement_id": requirement_id,
        "requirement_version": 1,
        "analysis_count": 1,
        "epic_count": 0,
        "feature_count": 0,
        "story_count": 0,
        "source_changed": True,
        "requires_acknowledgement": True,
    }
    assert client.put(f"/requirements/{requirement_id}", json=proposed).status_code == 409

    committed = client.put(
        f"/requirements/{requirement_id}",
        json={**proposed, "impact_acknowledged": True},
    )
    assert committed.status_code == 200
    assert committed.json()["version"] == 2
    assert client.get(f"/requirements/{requirement_id}/analysis").status_code == 404


def test_noop_source_update_needs_no_acknowledgement(client: TestClient) -> None:
    requirement = client.post(
        "/requirements", json={"title": "Title", "description": "Need"}
    ).json()
    requirement_id = requirement["id"]
    post_analysis(client, requirement_id)
    proposed = {
        "title": requirement["title"],
        "description": requirement["description"],
        "expected_version": requirement["version"],
    }

    preview = client.post(f"/requirements/{requirement_id}/impact-preview", json=proposed).json()
    assert preview["source_changed"] is False
    assert preview["requires_acknowledgement"] is False
    response = client.put(f"/requirements/{requirement_id}", json=proposed)
    assert response.status_code == 200
    assert response.json()["version"] == 1


def test_requirement_update_rejects_stale_expected_version(client: TestClient) -> None:
    requirement = client.post(
        "/requirements", json={"title": "Title", "description": "Need"}
    ).json()
    requirement_id = requirement["id"]
    response = client.put(
        f"/requirements/{requirement_id}",
        json={"title": "Changed", "description": "Need", "expected_version": 999},
    )
    assert response.status_code == 409
