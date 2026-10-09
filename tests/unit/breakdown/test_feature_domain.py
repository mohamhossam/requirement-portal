"""Tests for the Feature aggregate and the shared review lifecycle.

Feature inherits its lifecycle from ReviewableGeneration, so these tests are
deliberately the same shape as the Epic ones: if the shared rules ever change
for one aggregate and not the other, both suites should notice.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from smb_requirement_agent.breakdown.domain.epic.value_objects import EpicId
from smb_requirement_agent.breakdown.domain.feature.entities import Feature
from smb_requirement_agent.breakdown.domain.feature.errors import (
    InvalidFeatureContentError,
    StaleFeatureApprovalError,
)
from smb_requirement_agent.breakdown.domain.feature.value_objects import (
    DeliveryDrop,
    FeatureId,
    FeatureName,
    FeatureOutcome,
    FeatureStatus,
    SplittingPattern,
    SplittingRationale,
)
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.staleness import StaleReason

GENERATED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
CHANGED_AT = GENERATED_AT + timedelta(days=1)


def make_feature(status: FeatureStatus = FeatureStatus.GENERATED) -> Feature:
    return Feature(
        id=FeatureId("feature-1"),
        epic_id=EpicId("epic-1"),
        name=FeatureName("B2B portal bundle ordering"),
        outcome=FeatureOutcome("SMB customers can order the bundle in the B2B portal"),
        delivery_drop=DeliveryDrop.MVP,
        splitting_pattern=SplittingPattern.CHANNEL,
        splitting_rationale=SplittingRationale("The portal is a separate channel"),
        status=status,
        provenance=Provenance(generated_at=GENERATED_AT, model="fake", prompt_version="feature-v1"),
    )


def apply_edit(feature: Feature, *, source_reconciled: bool = False) -> Feature:
    """Apply a standard edit, so each test states only what it is asserting."""
    return feature.edit(
        name=FeatureName("Renamed"),
        outcome=FeatureOutcome("New outcome"),
        delivery_drop=DeliveryDrop.LATER,
        splitting_pattern=SplittingPattern.JOURNEY_STAGE,
        splitting_rationale=SplittingRationale("Reconsidered as a journey stage"),
        source_reconciled=source_reconciled,
    )


class TestValueObjects:
    @pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
    @pytest.mark.parametrize(
        "factory", [FeatureId, FeatureName, FeatureOutcome, SplittingRationale]
    )
    def test_blank_content_is_rejected(self, factory: type, blank: str) -> None:
        with pytest.raises(InvalidFeatureContentError):
            factory(blank)

    def test_surrounding_whitespace_is_normalised(self) -> None:
        assert FeatureName("  Ordering  ").value == "Ordering"


class TestLifecycle:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (FeatureStatus.GENERATED, False),
            (FeatureStatus.EDITED, True),
            (FeatureStatus.APPROVED, True),
        ],
    )
    def test_is_human_owned(self, status: FeatureStatus, expected: bool) -> None:
        assert make_feature(status).is_human_owned is expected

    def test_edit_sets_edited_status_and_new_content(self) -> None:
        edited = apply_edit(make_feature())

        assert edited.status is FeatureStatus.EDITED
        assert edited.name.value == "Renamed"
        assert edited.delivery_drop is DeliveryDrop.LATER
        assert edited.splitting_pattern is SplittingPattern.JOURNEY_STAGE

    def test_editing_approved_content_revokes_the_approval(self) -> None:
        approved = make_feature().approve()

        assert apply_edit(approved).status is FeatureStatus.EDITED

    def test_edit_preserves_provenance(self) -> None:
        feature = make_feature()

        assert apply_edit(feature).provenance == feature.provenance

    def test_edit_requires_explicit_stale_reconciliation(self) -> None:
        stale = make_feature().mark_stale(StaleReason.EPIC_CHANGED, CHANGED_AT)

        edited = apply_edit(stale)

        assert edited.is_stale

        reconciled = apply_edit(stale, source_reconciled=True)
        assert not reconciled.is_stale
        assert reconciled.approve().status is FeatureStatus.APPROVED

    def test_approval_is_idempotent(self) -> None:
        approved = make_feature().approve()

        assert approved.approve() is approved

    @pytest.mark.parametrize("reason", [StaleReason.REQUIREMENT_CHANGED, StaleReason.EPIC_CHANGED])
    def test_stale_feature_cannot_be_approved(self, reason: StaleReason) -> None:
        stale = make_feature().mark_stale(reason, CHANGED_AT)

        with pytest.raises(StaleFeatureApprovalError):
            stale.approve()

    def test_marking_stale_preserves_content_and_status(self) -> None:
        approved = make_feature().approve()

        stale = approved.mark_stale(StaleReason.EPIC_CHANGED, CHANGED_AT)

        assert stale.status is FeatureStatus.APPROVED
        assert stale.name == approved.name
        assert stale.staleness is not None
        assert stale.staleness.reason is StaleReason.EPIC_CHANGED

    def test_marking_stale_is_idempotent_and_keeps_the_first_divergence(self) -> None:
        stale = make_feature().mark_stale(StaleReason.REQUIREMENT_CHANGED, CHANGED_AT)

        again = stale.mark_stale(StaleReason.EPIC_CHANGED, CHANGED_AT + timedelta(days=5))

        assert again is stale
