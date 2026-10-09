"""Reusable HTTP steps for tests that need a confirmed analysis."""

from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response

from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


def post_analysis(
    client: TestClient,
    requirement_id: str,
    *,
    force: bool = False,
    headers: dict[str, str] | None = None,
) -> Response:
    requirement = client.get(f"/requirements/{requirement_id}", headers=headers).json()
    return client.post(
        f"/requirements/{requirement_id}/analysis",
        json={"context_token": requirement["analysis_context_token"], "force": force},
        headers=headers,
    )


def post_epic(
    client: TestClient,
    requirement_id: str,
    *,
    force: bool = False,
    headers: dict[str, str] | None = None,
) -> Response:
    analysis = client.get(f"/requirements/{requirement_id}/analysis", headers=headers).json()
    return client.post(
        f"/requirements/{requirement_id}/epic",
        json={"context_token": analysis["epic_context_token"], "force": force},
        headers=headers,
    )


def post_epic_approval(
    client: TestClient,
    requirement_id: str,
    *,
    headers: dict[str, str] | None = None,
) -> Response:
    epic = client.get(f"/requirements/{requirement_id}/epic", headers=headers).json()
    return client.post(
        f"/requirements/{requirement_id}/epic/approval",
        json={
            "expected_version": epic["version"],
            "expected_content_fingerprint": epic["content_fingerprint"],
        },
        headers=headers,
    )


def post_features(
    client: TestClient,
    requirement_id: str,
    *,
    force: bool = False,
    headers: dict[str, str] | None = None,
) -> Response:
    epic = client.get(f"/requirements/{requirement_id}/epic", headers=headers).json()
    return client.post(
        f"/requirements/{requirement_id}/features",
        json={"context_token": epic["feature_context_token"], "force": force},
        headers=headers,
    )


def post_feature_approval(
    client: TestClient,
    requirement_id: str,
    feature_id: str,
    *,
    headers: dict[str, str] | None = None,
) -> Response:
    features = client.get(f"/requirements/{requirement_id}/features", headers=headers).json()
    feature = next(item for item in features["features"] if item["id"] == feature_id)
    return client.post(
        f"/requirements/{requirement_id}/features/{feature_id}/approval",
        json={
            "expected_version": feature["version"],
            "expected_content_fingerprint": feature["content_fingerprint"],
        },
        headers=headers,
    )


def post_stories(
    client: TestClient,
    requirement_id: str,
    feature_id: str,
    *,
    headers: dict[str, str] | None = None,
) -> Response:
    features = client.get(f"/requirements/{requirement_id}/features", headers=headers).json()
    feature = next(item for item in features["features"] if item["id"] == feature_id)
    return client.post(
        f"/requirements/{requirement_id}/features/{feature_id}/stories",
        json={"context_token": feature["story_context_token"]},
        headers=headers,
    )


def screen_current_knowledge(client: TestClient, requirement_id: str) -> None:
    """Complete the current deterministic knowledge screen in synchronous API tests."""
    container = cast(Container, cast(FastAPI, client.app).state.container)
    typed_id = RequirementId(requirement_id)
    review = container.get_knowledge_review.execute(typed_id)
    access = container.access_repository.get_requirement(typed_id)
    assert access is not None and access.owner is not None
    actor = container.actor_directory.get(access.owner.actor.id)
    assert actor is not None
    drain_requirement_index(container)
    container.screen_requirement_knowledge.execute(actor, typed_id, review.current_fingerprint)


def confirm_fake_analysis(client: TestClient, requirement_id: str) -> None:
    """Resolve the deterministic fake findings and record human confirmation."""
    current = client.get(f"/requirements/{requirement_id}/analysis").json()
    response = client.post(
        f"/requirements/{requirement_id}/analysis/clarifications",
        json={
            "answers": [
                {"kind": "assumption", "subject": "This is an assumption.", "answer": "Confirmed."},
                {"kind": "open_question", "subject": "Is this a question?", "answer": "Yes."},
                {
                    "kind": "ambiguity",
                    "subject": "This is ambiguous.",
                    "answer": "Use the first interpretation.",
                },
                {
                    "kind": "potential_dependency",
                    "subject": "This is a dependency.",
                    "answer": "Available.",
                },
            ],
            "expected_analysis_version": current["version"],
        },
    )
    assert response.status_code == 200
    for proposal in response.json()["business_intent"]["proposals"]:
        if proposal["status"] == "pending":
            decided = client.patch(
                f"/requirements/{requirement_id}/analysis/proposals/{proposal['id']}",
                json={"decision": "accepted", "expected_version": proposal["version"]},
            )
            assert decided.status_code == 200
    screen_current_knowledge(client, requirement_id)
    current = client.get(f"/requirements/{requirement_id}/analysis").json()
    assert (
        client.post(
            f"/requirements/{requirement_id}/analysis/confirmation",
            json={"expected_version": current["version"]},
        ).status_code
        == 200
    )


def generate_story_tree(client: TestClient) -> tuple[str, str, list[dict[str, object]]]:
    """Create one confirmed tree with an approved Feature and generated Stories."""
    requirement_id = client.post(
        "/requirements",
        json={"title": "Stories", "description": "Generate reviewable Stories"},
    ).json()["id"]
    requirement = client.get(f"/requirements/{requirement_id}").json()
    analysis = client.post(
        f"/requirements/{requirement_id}/analysis",
        json={"context_token": requirement["analysis_context_token"]},
    )
    assert analysis.status_code == 200
    confirm_fake_analysis(client, requirement_id)
    analysis = client.get(f"/requirements/{requirement_id}/analysis").json()
    epic_response = client.post(
        f"/requirements/{requirement_id}/epic",
        json={"context_token": analysis["epic_context_token"]},
    )
    assert epic_response.status_code == 201
    epic = epic_response.json()
    approved_epic = client.post(
        f"/requirements/{requirement_id}/epic/approval",
        json={
            "expected_version": epic["version"],
            "expected_content_fingerprint": epic["content_fingerprint"],
        },
    )
    assert approved_epic.status_code == 200
    current_epic = client.get(f"/requirements/{requirement_id}/epic").json()
    features_response = client.post(
        f"/requirements/{requirement_id}/features",
        json={"context_token": current_epic["feature_context_token"]},
    )
    assert features_response.status_code == 201, features_response.text
    features = features_response.json()["features"]
    feature_id = features[0]["id"]
    approved_feature = client.post(
        f"/requirements/{requirement_id}/features/{feature_id}/approval",
        json={
            "expected_version": features[0]["version"],
            "expected_content_fingerprint": features[0]["content_fingerprint"],
        },
    )
    assert approved_feature.status_code == 200
    current_features = client.get(f"/requirements/{requirement_id}/features").json()["features"]
    current_feature = next(item for item in current_features if item["id"] == feature_id)
    stories = client.post(
        f"/requirements/{requirement_id}/features/{feature_id}/stories",
        json={"context_token": current_feature["story_context_token"]},
    ).json()["stories"]
    return str(requirement_id), str(feature_id), stories


def approve_fake_breakdown(
    client: TestClient,
) -> tuple[str, list[dict[str, object]], int]:
    """Create and formally approve a complete fake-provider backlog."""
    requirement_id = client.post(
        "/requirements",
        json={"title": "Portable backlog", "description": "Export an approved backlog."},
    ).json()["id"]
    requirement = client.get(f"/requirements/{requirement_id}").json()
    analysis_response = client.post(
        f"/requirements/{requirement_id}/analysis",
        json={"context_token": requirement["analysis_context_token"]},
    )
    assert analysis_response.status_code == 200
    confirm_fake_analysis(client, requirement_id)
    analysis = client.get(f"/requirements/{requirement_id}/analysis").json()
    epic_response = client.post(
        f"/requirements/{requirement_id}/epic",
        json={"context_token": analysis["epic_context_token"]},
    )
    assert epic_response.status_code == 201
    epic = epic_response.json()
    approved_epic = client.post(
        f"/requirements/{requirement_id}/epic/approval",
        json={
            "expected_version": epic["version"],
            "expected_content_fingerprint": epic["content_fingerprint"],
        },
    )
    assert approved_epic.status_code == 200
    current_epic = client.get(f"/requirements/{requirement_id}/epic").json()
    features_response = client.post(
        f"/requirements/{requirement_id}/features",
        json={"context_token": current_epic["feature_context_token"]},
    )
    assert features_response.status_code == 201, features_response.text
    features = features_response.json()["features"]
    stories: list[dict[str, object]] = []
    for feature in features:
        feature_id = feature["id"]
        approved_feature = client.post(
            f"/requirements/{requirement_id}/features/{feature_id}/approval",
            json={
                "expected_version": feature["version"],
                "expected_content_fingerprint": feature["content_fingerprint"],
            },
        )
        assert approved_feature.status_code == 200
        current_features = client.get(f"/requirements/{requirement_id}/features").json()["features"]
        current_feature = next(item for item in current_features if item["id"] == feature_id)
        generated = client.post(
            f"/requirements/{requirement_id}/features/{feature_id}/stories",
            json={"context_token": current_feature["story_context_token"]},
        ).json()["stories"]
        for story in generated:
            assert (
                client.post(
                    f"/requirements/{requirement_id}/features/{feature_id}/stories/"
                    f"{story['id']}/approval",
                    json={
                        "expected_version": story["version"],
                        "expected_content_fingerprint": story["content_fingerprint"],
                    },
                ).status_code
                == 200
            )
            stories.append({**story, "feature_id": feature_id})
    assert client.post(f"/requirements/{requirement_id}/breakdown-review").status_code == 200
    workflow = client.get(f"/requirements/{requirement_id}/approval-workflow").json()
    submitted = client.post(
        f"/requirements/{requirement_id}/review-submission",
        json={
            "expected_fingerprint": workflow["subject_fingerprint"],
            "expected_version": workflow["review_version"],
        },
    )
    assert submitted.status_code == 200
    approved = client.post(
        f"/requirements/{requirement_id}/breakdown-approval",
        json={
            "expected_fingerprint": submitted.json()["subject_fingerprint"],
            "expected_version": submitted.json()["review_version"],
            "rationale": "Approved for portable export.",
        },
    )
    assert approved.status_code == 200
    history = client.get(f"/requirements/{requirement_id}/revisions").json()
    revision = next(
        item["number"] for item in reversed(history["breakdown_revisions"]) if item["exportable"]
    )
    return str(requirement_id), stories, int(revision)


def drain_requirement_index(container: Container) -> None:
    """Explicitly drive the independent indexer in synchronous workflow tests."""
    import time

    for _ in range(1000):
        if container.requirement_indexer.ready():
            return
        if not container.requirement_indexer.process_next():
            time.sleep(0.01)  # A TestClient worker may own the current batch lease.
    raise AssertionError("Requirement index did not become ready")
