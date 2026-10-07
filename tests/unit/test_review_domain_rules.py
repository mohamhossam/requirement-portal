"""Governance rules as domain code (ADR-0103 §4, PR 6)."""

from __future__ import annotations

from dataclasses import replace

from smb_requirement_agent.domain.review.entities import (
    BreakdownReview,
    BreakdownStatus,
    FlagStatus,
)
from smb_requirement_agent.domain.review.evidence import ReviewEvidence
from smb_requirement_agent.domain.review.policy import ApprovalPolicy
from smb_requirement_agent.domain.review.readiness import (
    approval_subject,
    artifact_states,
    readiness_reasons,
)
from tests.characterisation import samples

# The sample review is under review: submitted as SHA_B, built from evidence SHA_A.
SUBMITTED = samples.SHA_B
EVIDENCE = samples.SHA_A


def test_an_unsubmitted_review_reads_as_it_is() -> None:
    review = replace(samples.review(), status=BreakdownStatus.GENERATED, submitted_fingerprint=None)

    assert review.effective_status("anything", "anything") is BreakdownStatus.GENERATED


def test_a_submission_whose_subject_and_evidence_hold_is_still_under_review() -> None:
    assert samples.review().effective_status(SUBMITTED, EVIDENCE) is BreakdownStatus.UNDER_REVIEW


def test_a_submission_reads_as_needing_revision_once_its_subject_or_evidence_moves() -> None:
    review = samples.review()

    assert review.effective_status(samples.SHA_C, EVIDENCE) is BreakdownStatus.NEEDS_REVISION
    assert review.effective_status(SUBMITTED, samples.SHA_C) is BreakdownStatus.NEEDS_REVISION
    assert review.effective_status(None, EVIDENCE) is BreakdownStatus.NEEDS_REVISION


def test_an_approval_whose_subject_moved_reads_as_needing_revision() -> None:
    approved = replace(samples.review(), status=BreakdownStatus.APPROVED)

    assert approved.effective_status(SUBMITTED, EVIDENCE) is BreakdownStatus.APPROVED
    assert approved.effective_status(samples.SHA_C, EVIDENCE) is BreakdownStatus.NEEDS_REVISION


def _rebuilt(evidence_fingerprint: str) -> BreakdownReview:
    """The sample review as the policy would rebuild it: no decisions, flags open, unsubmitted."""
    existing = samples.review()
    return replace(
        existing,
        evidence_fingerprint=evidence_fingerprint,
        decisions=(),
        flags=tuple(
            replace(item, status=FlagStatus.OPEN, resolution_decision_id=None)
            for item in existing.flags
        ),
        status=BreakdownStatus.GENERATED,
        submitted_fingerprint=None,
        approvals=(),
        comments=(),
        version=1,
    )


def test_carrying_forward_keeps_decisions_submission_approvals_and_comments() -> None:
    existing = samples.review()
    carried = _rebuilt(EVIDENCE).carry_forward_from(existing)

    assert carried.decisions == existing.decisions
    assert carried.flags == existing.flags
    assert carried.status is BreakdownStatus.UNDER_REVIEW
    assert carried.submitted_fingerprint == SUBMITTED
    assert carried.approvals == existing.approvals
    assert carried.comments == existing.comments
    assert carried.version == existing.version + 1


def test_carrying_forward_onto_changed_evidence_needs_revision() -> None:
    existing = samples.review()

    carried = _rebuilt(samples.SHA_C).carry_forward_from(existing)

    assert carried.status is BreakdownStatus.NEEDS_REVISION
    assert carried.submitted_fingerprint == SUBMITTED
    assert carried.version == existing.version + 1


def test_the_knowledge_version_is_recorded_without_other_change() -> None:
    review = samples.review()

    recorded = review.with_knowledge_version("catalogue-8")

    assert recorded.knowledge_version == "catalogue-8"
    assert replace(recorded, knowledge_version=review.knowledge_version) == review


def test_readiness_lists_every_reason_an_incomplete_breakdown_is_not_ready() -> None:
    evidence = ReviewEvidence(samples.requirement(), samples.analysis(), None, (), ())

    reasons = readiness_reasons(evidence, samples.review(), artifact_states(evidence))

    assert reasons == (
        "The breakdown has no Epic.",
        "The breakdown has no Features.",
        "The breakdown review is stale and must be refreshed.",
    )
    assert approval_subject(evidence, samples.review()) is None


def test_every_open_blocker_prevents_final_approval() -> None:
    reasons = ApprovalPolicy().blocking_reasons(samples.review(), active_blocking_questions=1)

    assert reasons == (
        "1 blocking review flag(s) remain open.",
        "1 blocking clarification question(s) remain open.",
    )
