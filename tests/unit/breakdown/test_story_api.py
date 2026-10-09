"""End-to-end HTTP behavior for Feature-scoped Story review."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.job_driver import JobRun, run_job
from tests.unit.workflow_helpers import (
    confirm_fake_analysis,
    post_analysis,
    post_epic,
    post_epic_approval,
    post_feature_approval,
    post_features,
    post_stories,
)

STORY_INPUT = {
    "role": "account manager",
    "action": "place an eligible order",
    "value": "the customer receives the requested service",
    "acceptance_criteria": [
        {"given": "an eligible customer", "when": "I submit", "then": "the order is accepted"}
    ],
}


def _features(client: TestClient, requirement_id: str) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = client.get(f"/requirements/{requirement_id}/features").json()[
        "features"
    ]
    return features


def _propose_split(
    client: TestClient, requirement_id: str, feature_id: str, story_id: str
) -> JobRun:
    base = f"/requirements/{requirement_id}/features/{feature_id}/stories"
    return run_job(
        client,
        requirement_id,
        "propose_story_change",
        context_token=client.get(base).json()["generation_context_token"],
        feature_id=feature_id,
        change_operation="split",
        source_story_ids=[story_id],
    )


def _approved_feature(client: TestClient) -> tuple[str, str]:
    requirement_id = client.post(
        "/requirements", json={"title": "Stories", "description": "Generate reviewable Stories"}
    ).json()["id"]
    assert post_analysis(client, requirement_id).succeeded
    confirm_fake_analysis(client, requirement_id)
    assert post_epic(client, requirement_id).succeeded
    assert post_epic_approval(client, requirement_id).status_code == 200
    assert post_features(client, requirement_id).succeeded
    feature_id = _features(client, requirement_id)[0]["id"]
    assert post_feature_approval(client, requirement_id, feature_id).status_code == 200
    return requirement_id, feature_id


def _generated(client: TestClient) -> tuple[str, str, list[dict[str, object]]]:
    requirement_id, feature_id = _approved_feature(client)
    run = post_stories(client, requirement_id, feature_id)
    assert run.succeeded, run.job
    stories: list[dict[str, object]] = client.get(
        f"/requirements/{requirement_id}/features/{feature_id}/stories"
    ).json()["stories"]
    return requirement_id, feature_id, stories


def test_empty_collection_is_200_and_generation_is_structured(client: TestClient) -> None:
    requirement_id, feature_id = _approved_feature(client)
    path = f"/requirements/{requirement_id}/features/{feature_id}/stories"
    empty = client.get(path).json()
    assert empty["feature_id"] == feature_id
    assert empty["stories"] == []
    assert empty["set_version"] == 1
    assert empty["generation_context_token"].startswith("generation-context-v2:")

    run = post_stories(client, requirement_id, feature_id)
    assert run.succeeded, run.job
    first = client.get(path).json()["stories"][0]
    assert first["voice"].startswith("As a ")
    assert first["acceptance_criteria"][0].keys() == {"given", "when", "then"}
    assert first["status"] == "generated"
    assert post_stories(client, requirement_id, feature_id).start.status_code == 409


def test_sibling_feature_approval_does_not_stale_story_generation_context(
    client: TestClient,
) -> None:
    requirement_id = client.post(
        "/requirements",
        json={"title": "Parallel review", "description": "Approve Features during generation"},
    ).json()["id"]
    assert post_analysis(client, requirement_id).succeeded
    confirm_fake_analysis(client, requirement_id)
    assert post_epic(client, requirement_id).succeeded
    assert post_epic_approval(client, requirement_id).status_code == 200
    assert post_features(client, requirement_id).succeeded
    features = _features(client, requirement_id)
    assert len(features) >= 2
    target_id = features[0]["id"]
    sibling_id = features[1]["id"]

    token_before_target_approval = features[0]["story_context_token"]
    assert post_feature_approval(client, requirement_id, target_id).status_code == 200
    current = _features(client, requirement_id)
    target_token = next(item["story_context_token"] for item in current if item["id"] == target_id)
    assert target_token != token_before_target_approval

    assert post_feature_approval(client, requirement_id, sibling_id).status_code == 200
    after_sibling_approval = _features(client, requirement_id)
    assert (
        next(
            item["story_context_token"]
            for item in after_sibling_approval
            if item["id"] == target_id
        )
        == target_token
    )
    generated = run_job(
        client,
        requirement_id,
        "generate_stories",
        context_token=target_token,
        feature_id=target_id,
    )
    assert generated.succeeded, generated.job


def test_edit_and_guarded_individual_regeneration_preserve_identity_and_siblings(
    client: TestClient,
) -> None:
    requirement_id, feature_id, stories = _generated(client)
    first_id, sibling_id = stories[0]["id"], stories[1]["id"]
    path = f"/requirements/{requirement_id}/features/{feature_id}/stories/{first_id}"
    assert (
        client.put(path, json={**STORY_INPUT, "expected_version": stories[0]["version"]}).json()[
            "status"
        ]
        == "edited"
    )
    current = client.get(f"/requirements/{requirement_id}/features/{feature_id}/stories").json()
    token = next(item for item in current["stories"] if item["id"] == first_id)[
        "story_context_token"
    ]
    guarded = run_job(
        client,
        requirement_id,
        "regenerate_story",
        context_token=token,
        feature_id=feature_id,
        story_id=first_id,
    )
    assert guarded.failure is not None
    assert guarded.failure["code"] == "story_regeneration_conflict"

    forced = run_job(
        client,
        requirement_id,
        "regenerate_story",
        context_token=token,
        feature_id=feature_id,
        story_id=first_id,
        force=True,
    )
    assert forced.succeeded, forced.job
    regenerated = client.get(
        f"/requirements/{requirement_id}/features/{feature_id}/stories"
    ).json()["stories"]
    assert regenerated[0]["id"] == first_id
    assert regenerated[0]["status"] == "generated"
    assert regenerated[1]["id"] == sibling_id


def test_whole_set_regeneration_requires_force_and_mints_new_ids(client: TestClient) -> None:
    requirement_id, feature_id, stories = _generated(client)
    first_id = stories[0]["id"]
    client.put(
        f"/requirements/{requirement_id}/features/{feature_id}/stories/{first_id}",
        json={**STORY_INPUT, "expected_version": stories[0]["version"]},
    )
    path = f"/requirements/{requirement_id}/features/{feature_id}/stories"
    token = client.get(path).json()["generation_context_token"]
    guarded = run_job(
        client, requirement_id, "regenerate_story_set", context_token=token, feature_id=feature_id
    )
    assert guarded.failure is not None
    assert guarded.failure["code"] == "story_regeneration_conflict"
    forced = run_job(
        client,
        requirement_id,
        "regenerate_story_set",
        context_token=token,
        feature_id=feature_id,
        force=True,
    )
    assert forced.succeeded, forced.job
    replacement = client.get(path).json()["stories"]
    assert {item["id"] for item in replacement}.isdisjoint({item["id"] for item in stories})


def test_manual_split_and_merge_preserve_the_primary_identity(client: TestClient) -> None:
    requirement_id, feature_id, stories = _generated(client)
    source_id = stories[0]["id"]
    base = f"/requirements/{requirement_id}/features/{feature_id}/stories"
    split = client.post(
        f"{base}/{source_id}/split",
        json={
            "replacements": [STORY_INPUT, {**STORY_INPUT, "action": "handle an exception"}],
            "expected_set_version": client.get(base).json()["set_version"],
        },
    )
    assert split.status_code == 200
    split_stories = split.json()["stories"]
    assert split_stories[0]["id"] == source_id
    assert split_stories[0]["status"] == "edited"

    merge_ids = [split_stories[0]["id"], split_stories[1]["id"]]
    merged = client.post(
        f"{base}/merge",
        json={
            "story_ids": merge_ids,
            "replacement": STORY_INPUT,
            "expected_set_version": split.json()["set_version"],
        },
    )
    assert merged.status_code == 200
    assert merged.json()["stories"][0]["id"] == source_id


def test_ai_proposal_is_previewed_and_conflicts_after_source_edit(client: TestClient) -> None:
    requirement_id, feature_id, stories = _generated(client)
    story_id = stories[0]["id"]
    base = f"/requirements/{requirement_id}/features/{feature_id}/stories"
    proposed = _propose_split(client, requirement_id, feature_id, str(story_id))
    assert proposed.succeeded, proposed.job
    proposals = client.get(f"{base}/change-proposals").json()
    assert len(proposals) == 1
    proposal_body = proposals[0]
    proposal_id = proposal_body["id"]
    assert len(proposal_body["candidates"]) >= 2

    client.put(
        f"{base}/{story_id}",
        json={**STORY_INPUT, "expected_version": stories[0]["version"]},
    )
    assert (
        client.post(
            f"{base}/change-proposals/{proposal_id}/application",
            json={
                "expected_version": proposal_body["version"],
                "expected_set_version": 1,
            },
        ).status_code
        == 409
    )


def test_applied_proposal_replaces_sources_and_is_removed(client: TestClient) -> None:
    requirement_id, feature_id, stories = _generated(client)
    base = f"/requirements/{requirement_id}/features/{feature_id}/stories"
    assert _propose_split(client, requirement_id, feature_id, str(stories[0]["id"])).succeeded
    proposal = client.get(f"{base}/change-proposals").json()[0]
    current_set_version = client.get(base).json()["set_version"]
    applied = client.post(
        f"{base}/change-proposals/{proposal['id']}/application",
        json={
            "expected_version": proposal["version"],
            "expected_set_version": current_set_version,
        },
    )
    assert applied.status_code == 200
    assert len(applied.json()["stories"]) == len(stories) + 1
    assert client.get(f"{base}/change-proposals").json() == []


def test_stale_stories_remain_readable_but_cannot_be_changed(client: TestClient) -> None:
    requirement_id, feature_id, stories = _generated(client)
    feature_edit = {
        "name": "Changed Feature",
        "outcome": "Changed outcome",
        "delivery_drop": "mvp",
        "splitting_pattern": "journey_stage",
        "splitting_rationale": "Changed source",
    }
    feature = next(
        item
        for item in client.get(f"/requirements/{requirement_id}/features").json()["features"]
        if item["id"] == feature_id
    )
    client.put(
        f"/requirements/{requirement_id}/features/{feature_id}",
        json={**feature_edit, "expected_version": feature["version"]},
    )
    base = f"/requirements/{requirement_id}/features/{feature_id}/stories"
    current = client.get(base)
    assert current.status_code == 200
    assert all(item["stale"]["reason"] == "feature_changed" for item in current.json()["stories"])
    assert (
        client.put(
            f"{base}/{stories[0]['id']}",
            json={**STORY_INPUT, "expected_version": stories[0]["version"]},
        ).status_code
        == 409
    )


def test_requirement_change_keeps_stale_stories_readable_without_current_analysis(
    client: TestClient,
) -> None:
    requirement_id, feature_id, stories = _generated(client)
    base = f"/requirements/{requirement_id}/features/{feature_id}/stories"
    edited = client.put(
        f"{base}/{stories[0]['id']}",
        json={**STORY_INPUT, "expected_version": stories[0]["version"]},
    ).json()
    approved = client.post(
        f"{base}/{stories[0]['id']}/approval",
        json={
            "expected_version": edited["version"],
            "expected_content_fingerprint": edited["content_fingerprint"],
        },
    ).json()
    assert _propose_split(client, requirement_id, feature_id, str(stories[1]["id"])).succeeded
    proposal = client.get(f"{base}/change-proposals").json()[0]
    client.put(
        f"/requirements/{requirement_id}",
        json={
            "title": "Updated",
            "description": "The upstream requirement changed",
            "expected_version": client.get(f"/requirements/{requirement_id}").json()["version"],
            "impact_acknowledged": True,
        },
    )
    response = client.get(base)
    assert response.status_code == 200
    current = response.json()["stories"]
    assert {item["id"] for item in current} == {item["id"] for item in stories}
    assert all(item["stale"]["reason"] == "requirement_changed" for item in current)
    retained = next(item for item in current if item["id"] == approved["id"])
    assert retained["role"] == STORY_INPUT["role"]
    assert retained["status"] == "approved"
    assert retained["approval_history"] == approved["approval_history"]
    assert [item["id"] for item in client.get(f"{base}/change-proposals").json()] == [
        proposal["id"]
    ]
