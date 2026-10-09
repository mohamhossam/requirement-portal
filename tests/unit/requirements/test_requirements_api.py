"""API integration tests for the Requirements endpoints.

Uses the shared `client` fixture, which wires a fresh container per test for
full isolation.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.workflow_helpers import post_analysis


class TestPostRequirements:
    def test_valid_request_returns_201(self, client: TestClient) -> None:
        response = client.post(
            "/requirements",
            json={
                "title": "High Speed Business Pro XGPON",
                "description": (
                    "The new bundles created with High Speed Internet "
                    "shall be available in channel for ordering."
                ),
            },
        )
        assert response.status_code == 201

    def test_response_contains_all_fields(self, client: TestClient) -> None:
        response = client.post(
            "/requirements",
            json={
                "title": "High Speed Business Pro XGPON",
                "description": "Detailed requirement description.",
            },
        )
        data = response.json()
        assert data["title"] == "High Speed Business Pro XGPON"
        assert data["description"] == "Detailed requirement description."
        assert data["status"] == "draft"
        assert "id" in data
        assert data["id"] != ""

    def test_empty_title_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/requirements",
            json={"title": "", "description": "Valid description."},
        )
        assert response.status_code == 422

    def test_blank_description_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/requirements",
            json={"title": "Valid Title", "description": "   "},
        )
        assert response.status_code == 422

    def test_missing_title_field_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/requirements",
            json={"description": "Description without title."},
        )
        assert response.status_code == 422


class TestGetRequirement:
    def test_existing_requirement_returns_200(self, client: TestClient) -> None:
        post = client.post(
            "/requirements",
            json={"title": "My Requirement", "description": "Description here."},
        )
        requirement_id = post.json()["id"]

        response = client.get(f"/requirements/{requirement_id}")

        assert response.status_code == 200
        assert response.json()["id"] == requirement_id
        assert response.json()["title"] == "My Requirement"

    def test_unknown_id_returns_404(self, client: TestClient) -> None:
        response = client.get("/requirements/nonexistent-id")
        assert response.status_code == 404


class TestListRequirements:
    def test_empty_list_returns_200_with_no_requirements(self, client: TestClient) -> None:
        response = client.get("/requirements")
        assert response.status_code == 200
        assert response.json() == {
            "requirements": [],
            "attention": [],
            "total": 0,
            "offset": 0,
            "limit": 20,
            "has_more": False,
            "status_counts": {
                "draft": 0,
                "needs_answers": 0,
                "reanalysing": 0,
                "ready_for_review": 0,
                "approved": 0,
                "needs_revision": 0,
                "stale": 0,
                "knowledge_review": 0,
                "duplicate": 0,
            },
            "owner_facets": [],
        }

    def test_lists_created_requirements_newest_first(self, client: TestClient) -> None:
        first = client.post(
            "/requirements",
            json={"title": "First requirement", "description": "The earlier one."},
        ).json()
        second = client.post(
            "/requirements",
            json={"title": "Second requirement", "description": "The later one."},
        ).json()

        response = client.get("/requirements")

        assert response.status_code == 200
        listed = response.json()["requirements"]
        assert [item["id"] for item in listed] == [second["id"], first["id"]]
        assert listed[0]["title"] == "Second requirement"
        assert listed[0]["status"] == "draft"
        assert listed[0]["workflow_status"] == "draft"
        assert listed[0]["next_action"] == "analyse"

    def test_search_status_sort_and_facets_are_server_backed(self, client: TestClient) -> None:
        alpha = client.post(
            "/requirements",
            json={"title": "Alpha coverage", "description": "XGPON channel rollout."},
        ).json()
        client.post(
            "/requirements",
            json={"title": "Beta billing", "description": "Invoice migration."},
        )
        post_analysis(client, alpha["id"])

        response = client.get(
            "/requirements",
            params=[
                ("q", "xgpon"),
                ("workflow_status", "needs_answers"),
                ("sort", "title_asc"),
            ],
        )

        assert response.status_code == 200
        body = response.json()
        assert [item["id"] for item in body["requirements"]] == [alpha["id"]]
        assert body["requirements"][0]["unresolved_items"] == 4
        assert body["status_counts"]["needs_answers"] == 1
        assert body["total"] == 1

    def test_pagination_metadata_and_limit_validation(self, client: TestClient) -> None:
        for index in range(3):
            client.post(
                "/requirements",
                json={"title": f"Requirement {index}", "description": "Description."},
            )

        first = client.get("/requirements", params={"limit": 2}).json()
        second = client.get("/requirements", params={"limit": 2, "offset": 2}).json()

        assert first["total"] == 3
        assert first["has_more"] is True
        assert len(first["requirements"]) == 2
        assert second["has_more"] is False
        assert len(second["requirements"]) == 1
        assert client.get("/requirements", params={"limit": 101}).status_code == 422


class TestPutRequirement:
    def test_valid_update_returns_200_with_updated_content(self, client: TestClient) -> None:
        post = client.post(
            "/requirements",
            json={"title": "Original Title", "description": "Original description."},
        )
        requirement_id = post.json()["id"]

        response = client.put(
            f"/requirements/{requirement_id}",
            json={
                "title": "Updated Title",
                "description": "Updated description.",
                "expected_version": post.json()["version"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["description"] == "Updated description."
        assert data["id"] == requirement_id

    def test_update_is_reflected_on_subsequent_get(self, client: TestClient) -> None:
        post = client.post(
            "/requirements",
            json={"title": "Original Title", "description": "Original description."},
        )
        requirement_id = post.json()["id"]

        client.put(
            f"/requirements/{requirement_id}",
            json={
                "title": "Updated Title",
                "description": "Updated description.",
                "expected_version": post.json()["version"],
            },
        )

        get_response = client.get(f"/requirements/{requirement_id}")
        assert get_response.json()["title"] == "Updated Title"
        assert get_response.json()["description"] == "Updated description."

    def test_unknown_id_returns_404(self, client: TestClient) -> None:
        response = client.put(
            "/requirements/nonexistent-id",
            json={"title": "Title", "description": "Description.", "expected_version": 1},
        )
        assert response.status_code == 404

    def test_empty_title_returns_422(self, client: TestClient) -> None:
        post = client.post(
            "/requirements",
            json={"title": "Title", "description": "Description."},
        )
        requirement_id = post.json()["id"]

        response = client.put(
            f"/requirements/{requirement_id}",
            json={"title": "", "description": "Valid description.", "expected_version": 1},
        )
        assert response.status_code == 422


class TestHealthStillWorks:
    def test_health_endpoint_unaffected(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
