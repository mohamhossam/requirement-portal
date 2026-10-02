"""Feature aggregate root."""

from __future__ import annotations

from dataclasses import dataclass, replace

from smb_requirement_agent.domain.architecture.entities import ArchitectureImpact
from smb_requirement_agent.domain.epic.value_objects import EpicId
from smb_requirement_agent.domain.feature.errors import StaleFeatureApprovalError
from smb_requirement_agent.domain.feature.value_objects import (
    DeliveryDrop,
    FeatureId,
    FeatureName,
    FeatureOutcome,
    SplittingPattern,
    SplittingRationale,
)
from smb_requirement_agent.domain.shared.actions import ActionAvailability
from smb_requirement_agent.domain.shared.approval import (
    Approval,
    ApprovalDecision,
    ApprovalTargetKind,
)
from smb_requirement_agent.domain.shared.errors import InvalidApprovalContentError
from smb_requirement_agent.domain.shared.generation import GenerationStatus, ReviewableGeneration


@dataclass(frozen=True, kw_only=True)
class Feature(ReviewableGeneration):
    """One customer-recognisable capability, traced to exactly one Epic.

    A Feature carries one measurable outcome intended to fit a single PI, and
    records why it was split out from its Epic. It is never written in
    user-story voice.

    The review lifecycle is inherited from ReviewableGeneration, so a Feature
    and an Epic cannot drift apart on what editing or approval mean.
    """

    id: FeatureId
    epic_id: EpicId
    name: FeatureName
    outcome: FeatureOutcome
    delivery_drop: DeliveryDrop
    splitting_pattern: SplittingPattern
    splitting_rationale: SplittingRationale

    review_label = "Feature"

    def story_availability(self) -> ActionAvailability:
        """Stories may be generated or changed only under a current, approved Feature."""
        if self.is_stale:
            return ActionAvailability.block(
                "Reconcile the stale Feature before generating or changing its Stories."
            )
        if self.status is not GenerationStatus.APPROVED:
            return ActionAvailability.block(
                "Approve the Feature before generating or changing its Stories."
            )
        return ActionAvailability.allow()

    architecture: ArchitectureImpact | None = None

    def edit(
        self,
        name: FeatureName,
        outcome: FeatureOutcome,
        delivery_drop: DeliveryDrop,
        splitting_pattern: SplittingPattern,
        splitting_rationale: SplittingRationale,
        *,
        source_reconciled: bool = False,
    ) -> Feature:
        """Return an edited copy, revoking approval and clearing staleness."""
        return self._edited(
            name=name,
            outcome=outcome,
            delivery_drop=delivery_drop,
            splitting_pattern=splitting_pattern,
            splitting_rationale=splitting_rationale,
            architecture=None,
            source_reconciled=source_reconciled,
        )

    def with_architecture(self, impact: ArchitectureImpact) -> Feature:
        """Attach a current mapping without changing content ownership or approval."""
        return replace(self, architecture=impact, version=self.version + 1)

    def approve(self, approval: Approval | None = None) -> Feature:
        """Return an approved copy.

        Refuses a stale Feature, for the same reason an Epic does: the Epic or
        requirement above it has moved on.
        """
        if self.is_stale:
            raise StaleFeatureApprovalError(
                f"Feature {self.id.value!r} is stale and cannot be approved. "
                "Edit or regenerate it against the current Epic first."
            )
        # Compatibility for legacy approved snapshots; formal governance use
        # cases always supply an attributed, fingerprint-bound Approval.
        if approval is None:
            return (
                self
                if self.status.value == "approved"
                else replace(self, status=type(self.status).APPROVED)
            )
        if (
            approval.decision is not ApprovalDecision.APPROVED
            or approval.target.kind is not ApprovalTargetKind.FEATURE
            or approval.target.item_id != self.id.value
        ):
            raise InvalidApprovalContentError("The approval does not target this Feature.")
        return self._approved(approval)
