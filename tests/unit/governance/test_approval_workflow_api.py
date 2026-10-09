"""End-to-end API coverage for Slice 9 governance."""

from dataclasses import replace

from fastapi.testclient import TestClient

from smb_requirement_agent.breakdown.domain.epic.value_objects import (
    BusinessCase,
    BusinessOutcome,
    EpicName,
)
from smb_requirement_agent.governance.domain.review.fingerprints import artifact_fingerprint
from smb_requirement_agent.interfaces.api.container import Container
from tests.job_driver import run_job
from tests.unit.breakdown.test_epic_domain import make_epic
from tests.unit.workflow_helpers import (
    confirm_fake_analysis,
    post_analysis,
    post_epic,
    post_epic_approval,
    post_feature_approval,
    post_features,
    post_stories,
)


def test_epic_fingerprint_covers_all_visible_business_content() -> None:
    epic = make_epic()
    baseline = artifact_fingerprint(epic)

    assert artifact_fingerprint(replace(epic, name=EpicName("Another name"))) != baseline
    assert (
        artifact_fingerprint(replace(epic, outcome=BusinessOutcome("Another outcome"))) != baseline
    )
    assert (
        artifact_fingerprint(replace(epic, business_case=BusinessCase("Another case"))) != baseline
    )


def _governable_tree(client: TestClient) -> tuple[str, list[dict[str, object]]]:
    requirement_id = client.post(
        "/requirements",
        json={"title": "Governed backlog", "description": "Review every generated item."},
    ).json()["id"]
    assert post_analysis(client, requirement_id).succeeded
    confirm_fake_analysis(client, requirement_id)
    assert post_epic(client, requirement_id).succeeded
    epic = client.get(f"/requirements/{requirement_id}/epic").json()
    assert post_epic_approval(client, requirement_id).status_code == 200
    assert post_features(client, requirement_id).succeeded
    features = client.get(f"/requirements/{requirement_id}/features").json()["features"]
    stories: list[dict[str, object]] = []
    for feature in features:
        feature_id = feature["id"]
        assert post_feature_approval(client, requirement_id, feature_id).status_code == 200
        assert post_stories(client, requirement_id, feature_id).succeeded
        generated = client.get(
            f"/requirements/{requirement_id}/features/{feature_id}/stories"
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
    assert epic["content_fingerprint"]
    assert run_job(client, requirement_id, "generate_breakdown_review").succeeded
    return str(requirement_id), stories


def test_owner_can_submit_comment_and_finally_approve(client: TestClient) -> None:
    requirement_id, stories = _governable_tree(client)
    workflow = client.get(f"/requirements/{requirement_id}/approval-workflow").json()

    assert workflow["readiness_reasons"] == []
    assert workflow["can_submit"] is True
    assert workflow["completion"]["stories_approved"] == workflow["completion"]["stories_total"]

    submitted = client.post(
        f"/requirements/{requirement_id}/review-submission",
        json={
            "expected_fingerprint": workflow["subject_fingerprint"],
            "expected_version": workflow["review_version"],
        },
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "under_review"

    commented = client.post(
        f"/requirements/{requirement_id}/breakdown-review/comments",
        json={
            "target_kind": "breakdown",
            "target_id": requirement_id,
            "body": "Ready for the final owner decision.",
            "expected_version": submitted.json()["review_version"],
        },
    )
    assert commented.status_code == 200
    assert commented.json()["comments"][0]["recorded_by"]["id"] == "fake-owner"

    approved = client.post(
        f"/requirements/{requirement_id}/breakdown-approval",
        json={
            "expected_fingerprint": submitted.json()["subject_fingerprint"],
            "expected_version": commented.json()["review_version"],
            "rationale": "All current evidence is acceptable.",
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["breakdown_approvals"][0]["recorded_by"]["id"] == "fake-owner"
    repeated = client.post(
        f"/requirements/{requirement_id}/breakdown-approval",
        json={
            "expected_fingerprint": submitted.json()["subject_fingerprint"],
            "expected_version": approved.json()["review_version"],
        },
    )
    assert repeated.status_code == 200
    assert len(repeated.json()["breakdown_approvals"]) == 1

    listed = client.get("/requirements").json()["requirements"][0]
    assert listed["workflow_status"] == "approved"

    story = stories[0]
    edited = client.put(
        f"/requirements/{requirement_id}/features/{story['feature_id']}/stories/{story['id']}",
        json={
            "role": story["role"],
            "action": f"{story['action']} with a reviewed failure path",
            "value": story["value"],
            "acceptance_criteria": story["acceptance_criteria"],
            "expected_version": client.get(
                f"/requirements/{requirement_id}/features/{story['feature_id']}/stories"
            ).json()["stories"][0]["version"],
        },
    )
    assert edited.status_code == 200
    invalidated = client.get(f"/requirements/{requirement_id}/approval-workflow")
    assert invalidated.status_code == 200
    assert invalidated.json()["status"] == "needs_revision"


def test_reviewer_can_reject_story_but_cannot_submit(client: TestClient) -> None:
    requirement_id, stories = _governable_tree(client)
    reviewer_headers = {"X-Fake-Actor-Id": "fake-reviewer"}
    access = client.get(f"/requirements/{requirement_id}/assignments").json()
    assert (
        client.put(
            f"/requirements/{requirement_id}/reviewers/fake-reviewer",
            json={"expected_version": access["version"]},
        ).status_code
        == 200
    )
    workflow = client.get(f"/requirements/{requirement_id}/approval-workflow").json()
    submitted = client.post(
        f"/requirements/{requirement_id}/review-submission",
        json={
            "expected_fingerprint": workflow["subject_fingerprint"],
            "expected_version": workflow["review_version"],
        },
    ).json()
    story = stories[0]

    rejected = client.post(
        f"/requirements/{requirement_id}/features/{story['feature_id']}/stories/"
        f"{story['id']}/rejection",
        headers=reviewer_headers,
        json={
            "expected_fingerprint": submitted["subject_fingerprint"],
            "expected_version": int(str(story["version"])) + 1,
            "expected_review_version": submitted["review_version"],
            "reason": "The acceptance criteria omit the failure path.",
        },
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "needs_revision"
    assert rejected.json()["approval_history"][-1]["decision"] == "rejected"
    after_rejection = client.get(
        f"/requirements/{requirement_id}/approval-workflow", headers=reviewer_headers
    ).json()
    assert after_rejection["status"] == "needs_revision"
    final_approval = client.post(
        f"/requirements/{requirement_id}/breakdown-approval",
        json={
            "expected_fingerprint": after_rejection["subject_fingerprint"],
            "expected_version": after_rejection["review_version"],
        },
    )
    assert final_approval.status_code == 409

    forbidden = client.post(
        f"/requirements/{requirement_id}/review-submission",
        headers=reviewer_headers,
        json={
            "expected_fingerprint": submitted["subject_fingerprint"],
            "expected_version": submitted["review_version"],
        },
    )
    assert forbidden.status_code == 403


def test_stale_fingerprint_and_observer_actions_are_rejected(client: TestClient) -> None:
    requirement_id, _ = _governable_tree(client)
    observer_headers = {"X-Fake-Actor-Id": "fake-observer"}

    conflict = client.post(
        f"/requirements/{requirement_id}/review-submission",
        json={
            "expected_fingerprint": "outdated",
            "expected_version": client.get(
                f"/requirements/{requirement_id}/approval-workflow"
            ).json()["review_version"],
        },
    )
    assert conflict.status_code == 409
    comment = client.post(
        f"/requirements/{requirement_id}/breakdown-review/comments",
        headers=observer_headers,
        json={
            "target_kind": "breakdown",
            "target_id": requirement_id,
            "body": "Observer comment",
            "expected_version": client.get(
                f"/requirements/{requirement_id}/approval-workflow"
            ).json()["review_version"],
        },
    )
    assert comment.status_code == 403


def test_legacy_approved_artifact_requires_attributed_reaffirmation(
    client: TestClient, container: Container
) -> None:
    requirement_id, _ = _governable_tree(client)
    requirement = container.requirement_repository.list_all()[0]
    epic = container.epic_repository.get_by_requirement_id(requirement.id)
    assert epic is not None
    container.epic_repository.save(replace(epic, approvals=(), version=epic.version + 1))

    workflow = client.get(f"/requirements/{requirement_id}/approval-workflow").json()
    assert (
        "Every Epic, Feature, and Story needs a current attributed approval."
        in workflow["readiness_reasons"]
    )

    assert post_epic_approval(client, requirement_id).status_code == 200
    refreshed = client.get(f"/requirements/{requirement_id}/approval-workflow").json()
    assert refreshed["readiness_reasons"] == []


def test_story_regeneration_resets_the_review_before_refreshing_it(client: TestClient) -> None:
    """The reset (StoriesChanged) runs before GenerationChecks refreshes the review.

    Reset first: needs_revision at +1, then the refresh saves +2. Refresh first: the refresh
    carries the new evidence to needs_revision at +1, and the reset then has nothing to do.
    Whole-feature regeneration gives the Stories new ids, so the evidence always changes.
    """
    requirement_id, stories = _governable_tree(client)
    workflow = client.get(f"/requirements/{requirement_id}/approval-workflow").json()
    submitted = client.post(
        f"/requirements/{requirement_id}/review-submission",
        json={
            "expected_fingerprint": workflow["subject_fingerprint"],
            "expected_version": workflow["review_version"],
        },
    )
    assert submitted.status_code == 200
    before = client.get(f"/requirements/{requirement_id}/breakdown-review").json()
    assert before["status"] == "under_review"

    base = f"/requirements/{requirement_id}/features/{stories[0]['feature_id']}/stories"
    token = client.get(base).json()["generation_context_token"]
    regenerated = run_job(
        client,
        requirement_id,
        "regenerate_story_set",
        context_token=token,
        feature_id=stories[0]["feature_id"],
        force=True,
    )
    assert regenerated.succeeded, regenerated.job

    after = client.get(f"/requirements/{requirement_id}/breakdown-review").json()
    assert after["status"] == "needs_revision"
    assert after["version"] == before["version"] + 2
