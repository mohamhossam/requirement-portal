"""Epic aggregate root."""

from __future__ import annotations

from dataclasses import dataclass, replace

from smb_requirement_agent.domain.epic.errors import StaleEpicApprovalError
from smb_requirement_agent.domain.epic.value_objects import (
    BusinessCase,
    BusinessOutcome,
    EpicId,
    EpicName,
)
from smb_requirement_agent.shared_kernel.actions import ActionAvailability
from smb_requirement_agent.shared_kernel.approval import (
    Approval,
    ApprovalDecision,
    ApprovalTargetKind,
)
from smb_requirement_agent.shared_kernel.errors import InvalidApprovalContentError
from smb_requirement_agent.shared_kernel.generation import GenerationStatus, ReviewableGeneration
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True, kw_only=True)
class Epic(ReviewableGeneration):
    """A portfolio-level business outcome derived from a requirement.

    An Epic describes a capability and its business case. It is never written
    in user-story voice, and it is not decomposed here.

    The review lifecycle - edit revokes approval and clears staleness, approval
    is idempotent, staleness preserves content - lives in ReviewableGeneration.
    """

    id: EpicId
    requirement_id: RequirementId
    name: EpicName
    outcome: BusinessOutcome
    business_case: BusinessCase

    review_label = "Epic"

    def decomposition_availability(self) -> ActionAvailability:
        """Only a current, approved Epic may be decomposed into Features."""
        if self.is_stale:
            return ActionAvailability.block(
                "Reconcile the stale Epic before decomposing it into Features."
            )
        if self.status is not GenerationStatus.APPROVED:
            return ActionAvailability.block("Approve the Epic before decomposing it into Features.")
        return ActionAvailability.allow()

    def edit(
        self,
        name: EpicName,
        outcome: BusinessOutcome,
        business_case: BusinessCase,
        *,
        source_reconciled: bool = False,
    ) -> Epic:
        """Return an edited copy, requiring explicit stale reconciliation."""
        return self._edited(
            name=name,
            outcome=outcome,
            business_case=business_case,
            source_reconciled=source_reconciled,
        )

    def approve(self, approval: Approval | None = None) -> Epic:
        """Return an approved copy.

        Refuses a stale Epic: approving content whose source has moved on is
        the failure this aggregate exists to prevent.
        """
        if self.is_stale:
            raise StaleEpicApprovalError(
                f"Epic {self.id.value!r} is stale and cannot be approved. "
                "Edit or regenerate it against the current requirement first."
            )
        # Pre-Slice-9 snapshots contain an approved lifecycle state without an
        # attributable decision. Keeping this narrow path preserves their
        # content until the application records the required reaffirmation.
        if approval is None:
            return (
                self
                if self.status.value == "approved"
                else replace(self, status=type(self.status).APPROVED)
            )
        if (
            approval.decision is not ApprovalDecision.APPROVED
            or approval.target.kind is not ApprovalTargetKind.EPIC
            or approval.target.item_id != self.id.value
        ):
            raise InvalidApprovalContentError("The approval does not target this Epic.")
        return self._approved(approval)
