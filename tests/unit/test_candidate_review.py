"""Governance's critique of unsaved Feature candidates (CandidateReviewPort, ADR-0103 PR 5)."""

from __future__ import annotations

from unittest.mock import Mock

from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.use_cases.breakdown_review import (
    GovernanceCandidateReview,
    RefreshSavedBreakdownReview,
)
from smb_requirement_agent.domain.review.evidence import ReviewEvidence
from smb_requirement_agent.domain.review.policy import BreakdownReviewPolicy
from tests.characterisation import samples


def test_critique_reports_what_the_review_policy_builds() -> None:
    """Generation feedback is unchanged by going through the port."""
    features = (samples.feature(), samples.second_feature())
    clock = FixedClock(samples.T3)
    expected = BreakdownReviewPolicy().build(
        ReviewEvidence(samples.requirement(), samples.analysis(), None, features, ()),
        (),
        clock.now(),
    )
    port = GovernanceCandidateReview(
        BreakdownReviewPolicy(), Mock(spec=RefreshSavedBreakdownReview), clock
    )

    critique = port.critique_features(samples.requirement(), samples.analysis(), features)

    assert expected.flags
    assert critique.has_flags is True
    assert critique.feedback == tuple(flag.detail for flag in expected.flags) + tuple(
        item.rationale for item in expected.recommendations
    )


def test_refresh_rebuilds_the_saved_review() -> None:
    refresher = Mock(spec=RefreshSavedBreakdownReview)
    port = GovernanceCandidateReview(BreakdownReviewPolicy(), refresher, FixedClock(samples.T3))

    port.refresh(samples.REQUIREMENT_ID)

    refresher.execute.assert_called_once_with(samples.REQUIREMENT_ID)
