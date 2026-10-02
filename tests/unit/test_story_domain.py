"""User Story domain invariants and lifecycle behavior."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.identity.entities import ActorId, ActorSnapshot
from smb_requirement_agent.domain.shared.approval import (
    Approval,
    ApprovalDecision,
    ApprovalId,
    ApprovalTarget,
    ApprovalTargetKind,
)
from smb_requirement_agent.domain.shared.generation import GenerationStatus, Provenance
from smb_requirement_agent.domain.shared.staleness import StaleReason
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.domain.story.errors import InvalidStoryContentError
from smb_requirement_agent.domain.story.value_objects import (
    AcceptanceCriterion,
    BusinessValue,
    DesiredAction,
    StoryId,
    UserRole,
)

NOW = datetime(2026, 1, 1, 12, tzinfo=UTC)


def make_story() -> UserStory:
    return UserStory(
        id=StoryId("story-1"),
        feature_id=FeatureId("feature-1"),
        role=UserRole("SMB customer"),
        action=DesiredAction("check service eligibility"),
        value=BusinessValue("I avoid an order that cannot be fulfilled"),
        acceptance_criteria=(
            AcceptanceCriterion("I have an address", "I check eligibility", "I see the result"),
        ),
        status=GenerationStatus.GENERATED,
        provenance=Provenance(NOW, "fake", "story-v1"),
    )


@pytest.mark.parametrize(
    "factory",
    [StoryId, UserRole, DesiredAction, BusinessValue],
)
@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_story_values_reject_blank_content(factory: type, blank: str) -> None:
    with pytest.raises(InvalidStoryContentError):
        factory(blank)


@pytest.mark.parametrize("field", ["given", "when", "then"])
def test_acceptance_criterion_requires_every_part(field: str) -> None:
    values = {"given": "context", "when": "action", "then": "outcome"}
    values[field] = "  "
    with pytest.raises(InvalidStoryContentError):
        AcceptanceCriterion(**values)


def test_story_requires_at_least_one_acceptance_criterion() -> None:
    story = make_story()
    with pytest.raises(InvalidStoryContentError):
        UserStory(
            id=story.id,
            feature_id=story.feature_id,
            role=story.role,
            action=story.action,
            value=story.value,
            acceptance_criteria=(),
            status=story.status,
            provenance=story.provenance,
        )


def test_story_voice_is_derived_from_structured_fields() -> None:
    assert make_story().voice == (
        "As a SMB customer, I want check service eligibility, "
        "so that I avoid an order that cannot be fulfilled."
    )


def test_edit_marks_human_owned_and_requires_explicit_reconciliation() -> None:
    story = make_story().mark_stale(StaleReason.FEATURE_CHANGED, NOW)
    edited = story.edit(
        UserRole("account manager"),
        DesiredAction("check customer eligibility"),
        BusinessValue("the order is valid"),
        (AcceptanceCriterion("a customer", "I check", "I see eligibility"),),
    )
    assert edited.status is GenerationStatus.EDITED
    assert edited.is_human_owned
    assert edited.staleness is not None

    reconciled = story.edit(
        UserRole("account manager"),
        DesiredAction("check customer eligibility"),
        BusinessValue("the order is valid"),
        (AcceptanceCriterion("a customer", "I check", "I see eligibility"),),
        source_reconciled=True,
    )
    assert reconciled.staleness is None
    assert edited.feature_id == story.feature_id


def test_rejection_preserves_content_and_can_be_followed_by_reapproval() -> None:
    actor = ActorSnapshot(ActorId("reviewer-1"), "Ravi Reviewer")
    target = ApprovalTarget(ApprovalTargetKind.STORY, "story-1")
    rejected = make_story().reject(
        Approval(
            ApprovalId("rejection-1"),
            target,
            ApprovalDecision.REJECTED,
            "fingerprint-1",
            actor,
            NOW,
            "Add the failure path.",
        )
    )

    assert rejected.status is GenerationStatus.NEEDS_REVISION
    assert rejected.voice == make_story().voice
    reapproved = rejected.approve(
        Approval(
            ApprovalId("approval-1"),
            target,
            ApprovalDecision.APPROVED,
            "fingerprint-2",
            actor,
            NOW,
        )
    )
    assert reapproved.status is GenerationStatus.APPROVED
    assert tuple(item.decision for item in reapproved.approvals) == (
        ApprovalDecision.REJECTED,
        ApprovalDecision.APPROVED,
    )


def test_rejection_revokes_an_approval_for_the_same_content() -> None:
    actor = ActorSnapshot(ActorId("reviewer-1"), "Ravi Reviewer")
    target = ApprovalTarget(ApprovalTargetKind.STORY, "story-1")
    fingerprint = "unchanged-content"
    approved = make_story().approve(
        Approval(
            ApprovalId("approval-1"),
            target,
            ApprovalDecision.APPROVED,
            fingerprint,
            actor,
            NOW,
        )
    )
    rejected = approved.reject(
        Approval(
            ApprovalId("rejection-1"),
            target,
            ApprovalDecision.REJECTED,
            fingerprint,
            actor,
            NOW,
            "Revise the failure path.",
        )
    )

    assert rejected.current_approval(fingerprint) is None
    reapproved = rejected.approve(
        Approval(
            ApprovalId("approval-2"),
            target,
            ApprovalDecision.APPROVED,
            fingerprint,
            actor,
            NOW,
        )
    )
    assert reapproved.current_approval(fingerprint) is not None
    assert len(reapproved.approvals) == 3
