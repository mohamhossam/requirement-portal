"""Slice 8 domain, application-policy, API, and audit behavior."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.errors import StoryQualityEvaluationError
from smb_requirement_agent.application.ports.story_quality_evaluator import (
    EMPTY_QUALITY_EVIDENCE,
    StoryQualityEvidence,
)
from smb_requirement_agent.domain.review.entities import (
    BreakdownReview,
    BreakdownStatus,
    Decision,
    DecisionId,
    Flag,
    FlagCategory,
    FlagId,
    FlagSeverity,
    FlagStatus,
    ResolutionPolicy,
    ReviewSource,
    ReviewSourceKind,
)
from smb_requirement_agent.domain.review.errors import (
    FlagResolutionConflictError,
    FlagResolutionNotAllowedError,
    InvalidReviewContentError,
)
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.domain.story.quality import (
    FindingSource,
    InvestCriterion,
    ValidationFinding,
)
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence.review_payloads import (
    review_from_payload,
    review_to_payload,
)
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorSnapshot,
)
from smb_requirement_agent.shared_kernel.approval import (
    Approval,
    ApprovalDecision,
    ApprovalId,
    ApprovalTarget,
    ApprovalTargetKind,
    ReviewComment,
)
from smb_requirement_agent.shared_kernel.errors import InvalidApprovalContentError
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.unit.workflow_helpers import generate_story_tree, post_analysis

NOW = datetime(2026, 9, 3, 12, tzinfo=UTC)


def _source() -> ReviewSource:
    return ReviewSource(ReviewSourceKind.STORY, "story-1", "As a user, I want value.")


def _flag(
    *,
    policy: ResolutionPolicy = ResolutionPolicy.DECISION,
    status: FlagStatus = FlagStatus.OPEN,
    decision_id: DecisionId | None = None,
) -> Flag:
    return Flag(
        FlagId("flag-1"),
        FlagCategory.QUALITY,
        FlagSeverity.BLOCKING,
        "Story quality",
        "The Story fails two INVEST criteria.",
        _source(),
        policy,
        status,
        decision_id,
    )


def _review(*flags: Flag, decisions: tuple[Decision, ...] = ()) -> BreakdownReview:
    return BreakdownReview(
        RequirementId("requirement-1"),
        NOW,
        "review-v1",
        "fingerprint",
        (),
        (),
        flags,
        (),
        decisions=decisions,
    )


def test_review_calculates_open_blockers_and_resolves_with_an_audited_decision() -> None:
    decision = Decision(
        DecisionId("decision-1"),
        "Accept for this delivery",
        "The dependency is already coordinated.",
        NOW,
        FlagId("flag-1"),
    )

    resolved = _review(_flag()).resolve(FlagId("flag-1"), decision)

    assert resolved.unresolved_blocker_count == 0
    assert resolved.flags[0].status is FlagStatus.RESOLVED
    assert resolved.decisions == (decision,)
    assert resolved.resolve(FlagId("flag-1"), decision) == resolved
    assert (
        resolved.resolve(
            FlagId("flag-1"),
            Decision(
                DecisionId("retry-decision"),
                decision.decision,
                decision.rationale,
                NOW,
                FlagId("flag-1"),
            ),
        )
        == resolved
    )
    with pytest.raises(FlagResolutionConflictError):
        resolved.resolve(
            FlagId("flag-1"),
            Decision(
                DecisionId("decision-2"),
                "Different",
                "Conflicting rationale",
                NOW,
                FlagId("flag-1"),
            ),
        )


def test_source_action_flag_cannot_be_dismissed() -> None:
    with pytest.raises(FlagResolutionNotAllowedError):
        _review(_flag(policy=ResolutionPolicy.SOURCE_ACTION)).resolve(
            FlagId("flag-1"),
            Decision(
                DecisionId("decision-1"),
                "Dismiss",
                "No source change",
                NOW,
                FlagId("flag-1"),
            ),
        )


def test_review_rejects_blank_or_dangling_audit_content() -> None:
    with pytest.raises(InvalidReviewContentError, match="must not be blank"):
        Decision(DecisionId("decision-1"), " ", "reason", NOW)
    with pytest.raises(InvalidReviewContentError, match="outside this review"):
        _review(
            _flag(),
            decisions=(
                Decision(
                    DecisionId("decision-1"),
                    "Decision",
                    "Reason",
                    NOW,
                    FlagId("another-flag"),
                ),
            ),
        )


def test_review_snapshot_round_trip_preserves_resolution_state() -> None:
    decision = Decision(
        DecisionId("decision-1"),
        "Accept",
        "Coordinated",
        NOW,
        FlagId("flag-1"),
    )
    review = _review(_flag()).resolve(FlagId("flag-1"), decision)

    assert review_from_payload(review_to_payload(review)) == review


def test_governance_transitions_and_snapshot_round_trip_are_auditable() -> None:
    actor = ActorSnapshot(ActorId("owner-1"), "Amina Owner")
    submitted = _review().submit("breakdown-sha")
    approval = Approval(
        ApprovalId("approval-1"),
        ApprovalTarget(ApprovalTargetKind.BREAKDOWN, "requirement-1"),
        ApprovalDecision.APPROVED,
        "breakdown-sha",
        actor,
        NOW,
        "Reviewed with the delivery team.",
    )
    comment = ReviewComment(
        "comment-1",
        ApprovalTarget(ApprovalTargetKind.BREAKDOWN, "requirement-1"),
        "Ready for final approval.",
        actor,
        NOW,
    )

    approved = submitted.add_comment(comment).approve_breakdown(approval)

    assert approved.status is BreakdownStatus.APPROVED
    assert approved.request_revision().status is BreakdownStatus.NEEDS_REVISION
    assert review_from_payload(review_to_payload(approved)) == approved


def test_rejection_requires_a_non_blank_rationale() -> None:
    with pytest.raises(InvalidApprovalContentError, match="rationale"):
        Approval(
            ApprovalId("approval-1"),
            ApprovalTarget(ApprovalTargetKind.STORY, "story-1"),
            ApprovalDecision.REJECTED,
            "story-sha",
            ActorSnapshot(ActorId("reviewer-1"), "Ravi Reviewer"),
            NOW,
            " ",
        )


def test_partial_analysis_review_separates_uncertainty_and_answers_open_question(
    client: TestClient,
) -> None:
    requirement_id = client.post(
        "/requirements",
        json={"title": "Review", "description": "Review uncertain work"},
    ).json()["id"]
    assert post_analysis(client, requirement_id).status_code == 200
    analysis = client.get(f"/requirements/{requirement_id}/analysis").json()

    created = client.post(f"/requirements/{requirement_id}/breakdown-review")

    assert created.status_code == 201
    body = created.json()
    assert body["fresh"] is True
    assert body["unresolved_blocker_count"] == 4
    assert body["unresolved_warning_count"] == 0
    assert body["dependencies"][0]["evidence_kind"] == "potential"
    assert {item["category"] for item in body["flags"]} == {
        "open_question",
        "assumption",
        "ambiguity",
        "dependency",
    }
    question = next(item for item in body["flags"] if item["category"] == "open_question")
    canonical_question = next(
        item for item in analysis["questions"] if item["kind"] == "open_question"
    )
    assert question["source"]["item_id"] == canonical_question["id"]
    assert question["severity"] == "blocking"
    assumption = next(item for item in body["flags"] if item["category"] == "assumption")
    disallowed = client.post(
        f"/requirements/{requirement_id}/breakdown-review/flags/{assumption['id']}/resolution",
        json={
            "decision": "Dismiss",
            "rationale": "No source action was taken.",
            "expected_fingerprint": body["evidence_fingerprint"],
            "expected_version": body["version"],
        },
    )
    assert disallowed.status_code == 409

    answered = client.post(
        f"/requirements/{requirement_id}/breakdown-review/open-questions/"
        f"{question['id']}/resolution",
        json={
            "answer": "Yes, the Business Owner confirmed it.",
            "expected_fingerprint": body["evidence_fingerprint"],
            "expected_version": body["version"],
        },
    )

    assert answered.status_code == 200
    assert answered.json()["review"]["fresh"] is False
    assert answered.json()["review"]["decisions"][0]["decision"] == "Answered open question"
    assert answered.json()["review"]["decisions"][0]["recorded_by"]["id"] == "fake-owner"
    history = client.get(f"/requirements/{requirement_id}/revisions").json()
    assert history["breakdown_revisions"][-1]["review_decision_count"] == 1

    refreshed = client.post(f"/requirements/{requirement_id}/breakdown-review")
    assert refreshed.status_code == 200
    assert all(item["category"] != "open_question" for item in refreshed.json()["flags"])


class ControllableQualityEvaluator:
    model = "controlled"
    prompt_version = "controlled-v1"

    def __init__(self) -> None:
        self.fail = False
        self.calls = 0

    def evaluate(
        self,
        story: UserStory,
        siblings: tuple[UserStory, ...],
        criteria: tuple[InvestCriterion, ...],
        *,
        evidence: StoryQualityEvidence = EMPTY_QUALITY_EVIDENCE,
    ) -> tuple[ValidationFinding, ...]:
        del story, siblings
        self.calls += 1
        if self.fail:
            raise StoryQualityEvaluationError("Quality provider failed.")
        return tuple(
            ValidationFinding(
                criterion,
                criterion not in {InvestCriterion.ESTIMABLE, InvestCriterion.SMALL},
                f"Evidence for {criterion.value}.",
                FindingSource.SEMANTIC,
            )
            for criterion in criteria
        )


def test_review_resolution_staleness_and_failed_refresh_preserve_last_success() -> None:
    evaluator = ControllableQualityEvaluator()
    container = build_container(
        Settings(llm_provider=LLMProvider.FAKE),
        story_quality_evaluator=evaluator,
    )
    with TestClient(create_app(lambda: container)) as client:
        requirement_id, feature_id, stories = generate_story_tree(client)
        created = client.post(f"/requirements/{requirement_id}/breakdown-review")
        assert created.status_code == 200
        body = created.json()
        quality_flag = next(item for item in body["flags"] if item["category"] == "quality")
        story_count = len(stories)
        assert evaluator.calls == story_count * 2

        resolution_url = (
            f"/requirements/{requirement_id}/breakdown-review/flags/{quality_flag['id']}/resolution"
        )
        resolution_request = {
            "decision": "Accept the delivery risk",
            "rationale": "The team has a bounded follow-up.",
            "expected_fingerprint": body["evidence_fingerprint"],
            "expected_version": body["version"],
        }
        resolved = client.post(resolution_url, json=resolution_request)
        assert resolved.status_code == 200
        assert resolved.json()["decisions"][0]["recorded_by"]["id"] == "fake-owner"
        assert (
            next(item for item in resolved.json()["flags"] if item["id"] == quality_flag["id"])[
                "status"
            ]
            == "resolved"
        )
        retried = client.post(resolution_url, json=resolution_request)
        assert retried.status_code == 409

        standalone = client.post(
            f"/requirements/{requirement_id}/breakdown-review/decisions",
            json={
                "decision": "Sequence fulfilment after ordering",
                "rationale": "The customer path should land first.",
                "expected_fingerprint": body["evidence_fingerprint"],
                "expected_version": resolved.json()["version"],
            },
        )
        assert standalone.status_code == 200
        assert len(standalone.json()["decisions"]) == 2

        story = stories[0]
        edited = client.put(
            f"/requirements/{requirement_id}/features/{feature_id}/stories/{story['id']}",
            json={
                "role": story["role"],
                "action": f"{story['action']} with a changed path",
                "value": story["value"],
                "acceptance_criteria": story["acceptance_criteria"],
                "expected_version": story["version"],
            },
        )
        assert edited.status_code == 200
        stale = client.post(
            f"/requirements/{requirement_id}/breakdown-review/decisions",
            json={
                "decision": "Old decision",
                "rationale": "Uses stale evidence.",
                "expected_fingerprint": body["evidence_fingerprint"],
                "expected_version": standalone.json()["version"],
            },
        )
        assert stale.status_code == 409
        assert (
            client.get(f"/requirements/{requirement_id}/breakdown-review").json()["fresh"] is False
        )

        evaluator.fail = True
        failed = client.post(f"/requirements/{requirement_id}/breakdown-review")
        assert failed.status_code == 502
        preserved = client.get(f"/requirements/{requirement_id}/breakdown-review").json()
        assert preserved["generated_at"] == body["generated_at"]
        assert len(preserved["decisions"]) == 2
