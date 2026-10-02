"""API tests for the Feature endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.workflow_helpers import (
    confirm_fake_analysis,
    post_analysis,
    post_epic,
    post_epic_approval,
    post_feature_approval,
    post_features,
)

EDIT_BODY = {
    "name": "Human name",
    "outcome": "Human outcome",
    "delivery_drop": "later",
    "splitting_pattern": "channel",
    "splitting_rationale": "Human rationale",
}


def _approved_epic(client: TestClient) -> str:
    created = client.post("/requirements", json={"title": "T", "description": "D"})
    requirement_id: str = created.json()["id"]
    assert post_analysis(client, requirement_id).status_code == 200
    confirm_fake_analysis(client, requirement_id)
    assert post_epic(client, requirement_id).status_code == 201
    assert post_epic_approval(client, requirement_id).status_code == 200
    return requirement_id


def _decomposed(client: TestClient) -> tuple[str, list[dict[str, object]]]:
    requirement_id = _approved_epic(client)
    response = post_features(client, requirement_id)
    assert response.status_code == 201
    features: list[dict[str, object]] = response.json()["features"]
    return requirement_id, features


class TestGenerate:
    def test_first_decomposition_returns_201(self, client: TestClient) -> None:
        requirement_id = _approved_epic(client)

        response = post_features(client, requirement_id)

        assert response.status_code == 201
        body = response.json()
        assert len(body["features"]) == 2
        assert body["features"][0]["splitting_pattern"] == "journey_stage"
        assert body["features"][0]["stale"] is None

    def test_regeneration_returns_200(self, client: TestClient) -> None:
        requirement_id, _ = _decomposed(client)

        assert post_features(client, requirement_id).status_code == 200

    def test_unapproved_epic_returns_409(self, client: TestClient) -> None:
        created = client.post("/requirements", json={"title": "T", "description": "D"})
        requirement_id = created.json()["id"]
        post_analysis(client, requirement_id)
        confirm_fake_analysis(client, requirement_id)
        post_epic(client, requirement_id)

        assert post_features(client, requirement_id).status_code == 409

    def test_missing_epic_returns_404(self, client: TestClient) -> None:
        created = client.post("/requirements", json={"title": "T", "description": "D"})
        requirement_id = created.json()["id"]
        post_analysis(client, requirement_id)

        assert (
            client.post(
                f"/requirements/{requirement_id}/features", json={"context_token": "unknown"}
            ).status_code
            == 409
        )

    def test_regenerating_over_approved_features_returns_409(self, client: TestClient) -> None:
        requirement_id, features = _decomposed(client)
        feature_id = str(features[0]["id"])
        post_feature_approval(client, requirement_id, feature_id)

        assert post_features(client, requirement_id).status_code == 409

    def test_force_replaces_the_set(self, client: TestClient) -> None:
        requirement_id, features = _decomposed(client)
        post_feature_approval(client, requirement_id, str(features[0]["id"]))

        response = post_features(client, requirement_id, force=True)

        assert response.status_code == 200
        assert all(f["status"] == "generated" for f in response.json()["features"])


class TestReadEditApprove:
    def test_get_returns_the_set(self, client: TestClient) -> None:
        requirement_id, _ = _decomposed(client)

        response = client.get(f"/requirements/{requirement_id}/features")

        assert response.status_code == 200
        assert len(response.json()["features"]) == 2

    def test_get_without_features_returns_404(self, client: TestClient) -> None:
        requirement_id = _approved_epic(client)

        assert client.get(f"/requirements/{requirement_id}/features").status_code == 404

    def test_edit_one_feature(self, client: TestClient) -> None:
        requirement_id, features = _decomposed(client)

        response = client.put(
            f"/requirements/{requirement_id}/features/{features[0]['id']}",
            json={**EDIT_BODY, "expected_version": features[0]["version"]},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "edited"
        assert response.json()["delivery_drop"] == "later"

    def test_blank_edit_returns_422(self, client: TestClient) -> None:
        requirement_id, features = _decomposed(client)

        response = client.put(
            f"/requirements/{requirement_id}/features/{features[0]['id']}",
            json={
                **EDIT_BODY,
                "name": "   ",
                "expected_version": features[0]["version"],
            },
        )

        assert response.status_code == 422

    def test_unsupported_pattern_returns_422(self, client: TestClient) -> None:
        requirement_id, features = _decomposed(client)

        response = client.put(
            f"/requirements/{requirement_id}/features/{features[0]['id']}",
            json={
                **EDIT_BODY,
                "splitting_pattern": "astrology",
                "expected_version": features[0]["version"],
            },
        )

        assert response.status_code == 422

    def test_unknown_feature_returns_404(self, client: TestClient) -> None:
        requirement_id, _ = _decomposed(client)

        response = client.put(
            f"/requirements/{requirement_id}/features/not-a-feature",
            json={**EDIT_BODY, "expected_version": 1},
        )

        assert response.status_code == 404

    def test_approval_returns_approved(self, client: TestClient) -> None:
        requirement_id, features = _decomposed(client)

        response = post_feature_approval(client, requirement_id, str(features[0]["id"]))

        assert response.status_code == 200
        assert response.json()["status"] == "approved"


def test_full_tree_flow_preserves_approved_features_when_the_requirement_changes(
    client: TestClient,
) -> None:
    """create -> analyse -> epic -> approve -> features -> edit -> approve -> update."""
    requirement_id, features = _decomposed(client)
    first, second = features[0]["id"], features[1]["id"]

    client.put(
        f"/requirements/{requirement_id}/features/{first}",
        json={**EDIT_BODY, "expected_version": features[0]["version"]},
    )
    approved = post_feature_approval(client, requirement_id, str(first)).json()
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

    body = client.get(f"/requirements/{requirement_id}/features").json()
    by_id = {f["id"]: f for f in body["features"]}

    assert by_id[first]["status"] == "approved", "approved work must survive"
    assert by_id[first]["name"] == "Human name"
    assert by_id[first]["stale"]["reason"] == "requirement_changed"
    assert by_id[second]["stale"]["reason"] == "requirement_changed"

    # The Epic above them is stale too, and the analysis is gone.
    assert client.get(f"/requirements/{requirement_id}/epic").json()["stale"] is not None
    assert client.get(f"/requirements/{requirement_id}/analysis").status_code == 404

    # A stale Feature cannot be re-approved until a human reconciles it.
    assert post_feature_approval(client, requirement_id, str(first)).status_code == 409
