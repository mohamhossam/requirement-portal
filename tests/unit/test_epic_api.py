"""API tests for the Epic endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.workflow_helpers import (
    confirm_fake_analysis,
    post_analysis,
    post_epic,
    post_epic_approval,
)

EDIT_BODY = {
    "name": "Human name",
    "outcome": "Human outcome",
    "business_case": "Human business case",
}


def _analysed_requirement(client: TestClient) -> str:
    created = client.post("/requirements", json={"title": "T", "description": "D"})
    requirement_id: str = created.json()["id"]
    assert post_analysis(client, requirement_id).status_code == 200
    confirm_fake_analysis(client, requirement_id)
    return requirement_id


class TestGenerate:
    def test_first_generation_returns_201(self, client: TestClient) -> None:
        requirement_id = _analysed_requirement(client)

        response = post_epic(client, requirement_id)

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "generated"
        assert body["stale"] is None
        assert body["provenance"]["prompt_version"]

    def test_regeneration_returns_200(self, client: TestClient) -> None:
        requirement_id = _analysed_requirement(client)
        post_epic(client, requirement_id)

        assert post_epic(client, requirement_id).status_code == 200

    def test_unknown_requirement_returns_404(self, client: TestClient) -> None:
        assert (
            client.post("/requirements/missing/epic", json={"context_token": "unknown"}).status_code
            == 404
        )

    def test_unanalysed_requirement_returns_404(self, client: TestClient) -> None:
        created = client.post("/requirements", json={"title": "T", "description": "D"})

        response = client.post(
            f"/requirements/{created.json()['id']}/epic", json={"context_token": "unknown"}
        )

        assert response.status_code == 409

    def test_unconfirmed_analysis_returns_409(self, client: TestClient) -> None:
        created = client.post("/requirements", json={"title": "T", "description": "D"})
        requirement_id = created.json()["id"]
        post_analysis(client, requirement_id)

        response = post_epic(client, requirement_id)

        assert response.status_code == 409
        assert "must be human-confirmed" in response.json()["message"]

    def test_regenerating_approved_content_returns_409(self, client: TestClient) -> None:
        requirement_id = _analysed_requirement(client)
        post_epic(client, requirement_id)
        post_epic_approval(client, requirement_id)

        assert post_epic(client, requirement_id).status_code == 409

    def test_force_regenerates_over_approved_content(self, client: TestClient) -> None:
        requirement_id = _analysed_requirement(client)
        post_epic(client, requirement_id)
        post_epic_approval(client, requirement_id)

        response = post_epic(client, requirement_id, force=True)

        assert response.status_code == 200
        assert response.json()["status"] == "generated"


class TestReadEditApprove:
    def test_get_returns_the_epic(self, client: TestClient) -> None:
        requirement_id = _analysed_requirement(client)
        post_epic(client, requirement_id)

        assert client.get(f"/requirements/{requirement_id}/epic").status_code == 200

    def test_get_without_an_epic_returns_404(self, client: TestClient) -> None:
        requirement_id = _analysed_requirement(client)

        assert client.get(f"/requirements/{requirement_id}/epic").status_code == 404

    def test_edit_returns_edited_content(self, client: TestClient) -> None:
        requirement_id = _analysed_requirement(client)
        post_epic(client, requirement_id)

        epic = client.get(f"/requirements/{requirement_id}/epic").json()
        response = client.put(
            f"/requirements/{requirement_id}/epic",
            json={**EDIT_BODY, "expected_version": epic["version"]},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "edited"
        assert response.json()["name"] == "Human name"

    def test_blank_edit_returns_422(self, client: TestClient) -> None:
        requirement_id = _analysed_requirement(client)
        post_epic(client, requirement_id)
        epic = client.get(f"/requirements/{requirement_id}/epic").json()

        response = client.put(
            f"/requirements/{requirement_id}/epic",
            json={**EDIT_BODY, "name": "   ", "expected_version": epic["version"]},
        )

        assert response.status_code == 422

    def test_approval_returns_approved_status(self, client: TestClient) -> None:
        requirement_id = _analysed_requirement(client)
        post_epic(client, requirement_id)

        response = post_epic_approval(client, requirement_id)

        assert response.status_code == 200
        assert response.json()["status"] == "approved"


def test_full_review_flow_preserves_approved_content_when_the_requirement_changes(
    client: TestClient,
) -> None:
    """create -> analyse -> generate -> edit -> approve -> update -> stale but intact."""
    requirement_id = _analysed_requirement(client)
    post_epic(client, requirement_id)
    epic = client.get(f"/requirements/{requirement_id}/epic").json()
    client.put(
        f"/requirements/{requirement_id}/epic",
        json={**EDIT_BODY, "expected_version": epic["version"]},
    )
    approved = post_epic_approval(client, requirement_id).json()
    assert approved["status"] == "approved"

    client.put(
        f"/requirements/{requirement_id}",
        json={
            "title": "Changed",
            "description": "Changed description",
            "expected_version": client.get(f"/requirements/{requirement_id}").json()["version"],
            "impact_acknowledged": True,
        },
    )

    epic = client.get(f"/requirements/{requirement_id}/epic").json()
    assert epic["status"] == "approved", "approved content must survive an upstream change"
    assert epic["name"] == "Human name"
    assert epic["stale"]["reason"] == "requirement_changed"

    # The analysis, being disposable, is gone.
    assert client.get(f"/requirements/{requirement_id}/analysis").status_code == 404

    # And a stale Epic cannot be re-approved until a human reconciles it.
    assert post_epic_approval(client, requirement_id).status_code == 409
