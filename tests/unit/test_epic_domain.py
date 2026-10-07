"""Tests for the Epic aggregate and its value objects."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.epic.errors import (
    InvalidEpicContentError,
    StaleEpicApprovalError,
)
from smb_requirement_agent.domain.epic.value_objects import (
    BusinessCase,
    BusinessOutcome,
    EpicId,
    EpicName,
    EpicProvenance,
    EpicStatus,
    StaleReason,
)
from smb_requirement_agent.shared_kernel.errors import InvalidGeneratedContentError
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

GENERATED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
CHANGED_AT = GENERATED_AT + timedelta(days=1)


def make_epic(status: EpicStatus = EpicStatus.GENERATED) -> Epic:
    return Epic(
        id=EpicId("epic-1"),
        requirement_id=RequirementId("req-1"),
        name=EpicName("Bundled SMB offer"),
        outcome=BusinessOutcome("SMB customers can order the bundle in channel"),
        business_case=BusinessCase("Grows bundle attach rate across the value stream"),
        status=status,
        provenance=EpicProvenance(
            generated_at=GENERATED_AT, model="gpt-4o", prompt_version="epic-v1"
        ),
    )


class TestValueObjects:
    @pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
    @pytest.mark.parametrize("factory", [EpicId, EpicName, BusinessOutcome, BusinessCase])
    def test_blank_content_is_rejected(self, factory: type, blank: str) -> None:
        with pytest.raises(InvalidEpicContentError):
            factory(blank)

    def test_surrounding_whitespace_is_normalised(self) -> None:
        assert EpicName("  Bundled offer  ").value == "Bundled offer"

    def test_provenance_rejects_a_naive_timestamp(self) -> None:
        with pytest.raises(InvalidGeneratedContentError, match="timezone-aware"):
            EpicProvenance(
                generated_at=datetime(2026, 1, 1, 12, 0),
                model="gpt-4o",
                prompt_version="epic-v1",
            )

    def test_provenance_rejects_blank_model(self) -> None:
        with pytest.raises(InvalidGeneratedContentError):
            EpicProvenance(generated_at=GENERATED_AT, model="  ", prompt_version="v1")


class TestHumanOwnership:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (EpicStatus.GENERATED, False),
            (EpicStatus.EDITED, True),
            (EpicStatus.APPROVED, True),
        ],
    )
    def test_is_human_owned(self, status: EpicStatus, expected: bool) -> None:
        assert make_epic(status).is_human_owned is expected


class TestEdit:
    def test_edit_sets_edited_status_and_new_content(self) -> None:
        edited = make_epic().edit(
            EpicName("Renamed"),
            BusinessOutcome("New outcome"),
            BusinessCase("New case"),
        )

        assert edited.status is EpicStatus.EDITED
        assert edited.name.value == "Renamed"

    def test_editing_approved_content_revokes_the_approval(self) -> None:
        """The approval attested to content that no longer exists."""
        approved = make_epic().approve()

        edited = approved.edit(
            EpicName("Renamed"), BusinessOutcome("New outcome"), BusinessCase("New case")
        )

        assert edited.status is EpicStatus.EDITED

    def test_edit_preserves_provenance(self) -> None:
        """An edit does not change what generated the Epic."""
        epic = make_epic()

        edited = epic.edit(
            EpicName("Renamed"), BusinessOutcome("New outcome"), BusinessCase("New case")
        )

        assert edited.provenance == epic.provenance

    def test_edit_requires_explicit_stale_reconciliation(self) -> None:
        stale = make_epic().mark_stale(StaleReason.REQUIREMENT_CHANGED, CHANGED_AT)

        edited = stale.edit(
            EpicName("Renamed"), BusinessOutcome("New outcome"), BusinessCase("New case")
        )

        assert edited.is_stale

        reconciled = stale.edit(
            EpicName("Renamed"),
            BusinessOutcome("New outcome"),
            BusinessCase("New case"),
            source_reconciled=True,
        )
        assert not reconciled.is_stale
        assert reconciled.approve().status is EpicStatus.APPROVED


class TestApprove:
    def test_generated_epic_can_be_approved(self) -> None:
        assert make_epic().approve().status is EpicStatus.APPROVED

    def test_approval_is_idempotent(self) -> None:
        approved = make_epic().approve()

        assert approved.approve() is approved

    def test_stale_epic_cannot_be_approved(self) -> None:
        stale = make_epic().mark_stale(StaleReason.REQUIREMENT_CHANGED, CHANGED_AT)

        with pytest.raises(StaleEpicApprovalError):
            stale.approve()


class TestMarkStale:
    def test_marking_stale_preserves_content_and_status(self) -> None:
        approved = make_epic().approve()

        stale = approved.mark_stale(StaleReason.REQUIREMENT_CHANGED, CHANGED_AT)

        assert stale.status is EpicStatus.APPROVED
        assert stale.name == approved.name
        assert stale.business_case == approved.business_case
        assert stale.staleness is not None
        assert stale.staleness.since == CHANGED_AT

    def test_marking_stale_is_idempotent_and_keeps_the_first_divergence(self) -> None:
        stale = make_epic().mark_stale(StaleReason.REQUIREMENT_CHANGED, CHANGED_AT)

        again = stale.mark_stale(StaleReason.REQUIREMENT_CHANGED, CHANGED_AT + timedelta(days=5))

        assert again is stale
