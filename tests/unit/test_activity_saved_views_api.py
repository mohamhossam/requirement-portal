from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

OWNER = {"X-Fake-Actor-Id": "fake-owner"}
OTHER = {"X-Fake-Actor-Id": "fake-reviewer"}


def test_activity_and_reports_require_authentication(client: TestClient) -> None:
    # Fake identity mode supplies its configured default persona; OIDC-mode
    # bearer enforcement is covered by the identity boundary tests.
    assert client.get("/activity").status_code == 200
    assert client.get("/reports/operational").status_code == 200
    assert client.get("/saved-views").status_code == 200


def test_requirement_creation_is_visible_in_activity_and_report(client: TestClient) -> None:
    created = client.post(
        "/requirements",
        headers=OWNER,
        json={"title": "Portfolio event", "description": "Trace this creation."},
    )
    assert created.status_code == 201
    requirement_id = created.json()["id"]

    activity = client.get(
        "/activity",
        headers=OTHER,
        params={"requirement_id": requirement_id, "action": "requirement_created"},
    )
    assert activity.status_code == 200
    payload = activity.json()
    assert payload["total"] == 1
    assert payload["items"][0]["requirement_id"] == requirement_id
    assert payload["items"][0]["actor"]["id"] == "fake-owner"
    assert payload["items"][0]["sources"][0]["kind"] == "requirement_revision"

    report = client.get("/reports/operational", headers=OTHER, params={"weeks": 4})
    assert report.status_code == 200, report.text
    assert report.json()["weeks"] == 4
    assert sum(week["requirements_created"]["value"] for week in report.json()["weekly"]) == 1


def test_saved_view_api_crud_conflicts_and_actor_isolation(client: TestClient) -> None:
    body: dict[str, Any] = {
        "name": "My queue",
        "criteria": {
            "query": "fibre",
            "workflow_statuses": ["needs_answers"],
            "sort": "title_asc",
            "owner_id": "fake-owner",
            "assigned_to_me": True,
        },
    }
    created = client.post("/saved-views", headers=OWNER, json=body)
    assert created.status_code == 201
    view = created.json()
    assert view["criteria"] == body["criteria"]

    duplicate = client.post("/saved-views", headers=OWNER, json={**body, "name": " MY QUEUE "})
    assert duplicate.status_code == 409
    assert client.get("/saved-views", headers=OTHER).json() == []

    hidden = client.put(
        f"/saved-views/{view['id']}",
        headers=OTHER,
        json={**body, "expected_version": 1},
    )
    assert hidden.status_code == 404

    updated = client.put(
        f"/saved-views/{view['id']}",
        headers=OWNER,
        json={
            "name": "Renamed queue",
            "criteria": {**body["criteria"], "query": None},
            "expected_version": 1,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    stale = client.delete(
        f"/saved-views/{view['id']}", headers=OWNER, params={"expected_version": 1}
    )
    assert stale.status_code == 409
    deleted = client.delete(
        f"/saved-views/{view['id']}", headers=OWNER, params={"expected_version": 2}
    )
    assert deleted.status_code == 204


def test_saved_view_blank_name_is_unprocessable(client: TestClient) -> None:
    response = client.post(
        "/saved-views",
        headers=OWNER,
        json={"name": "   ", "criteria": {}},
    )
    assert response.status_code == 422
