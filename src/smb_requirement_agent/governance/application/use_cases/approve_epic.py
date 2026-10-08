"""ApproveEpic use case."""

from __future__ import annotations

from smb_requirement_agent.application.errors import (
    ApprovalWorkflowNotReadyError,
    ArtifactVersionConflictError,
    EpicNotFoundError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.breakdown.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.governance.application.use_cases.approval_workflow import (
    ApprovalRecorder,
)
from smb_requirement_agent.governance.domain.review.fingerprints import artifact_fingerprint
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.approval import (
    ApprovalDecision,
    ApprovalTarget,
    ApprovalTargetKind,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class ApproveEpic:
    """Records a human sign-off on an Epic's current content."""

    def __init__(
        self,
        requirement_repository: RequirementRepositoryPort,
        epic_repository: EpicRepositoryPort,
        recorder: ApprovalRecorder,
        transactions: TransactionManagerPort,
    ) -> None:
        self._requirements = requirement_repository
        self._epics = epic_repository
        self._recorder = recorder
        self._transactions = transactions

    def execute(
        self,
        requirement_id: RequirementId,
        actor: ActorProfile,
        expected_version: int,
        expected_fingerprint: str,
        rationale: str | None = None,
    ) -> Epic:
        if self._requirements.get(requirement_id) is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")

        epic = self._epics.get_by_requirement_id(requirement_id)
        if epic is None:
            raise EpicNotFoundError(f"No Epic exists for requirement {requirement_id.value!r}.")
        self._recorder.require_member(requirement_id, actor)
        fingerprint = artifact_fingerprint(epic)
        if expected_fingerprint.strip() != fingerprint:
            raise ApprovalWorkflowNotReadyError(
                "The Epic changed. Reload it before approving the current content."
            )
        if epic.current_approval(fingerprint) is not None:
            return epic
        if epic.version != expected_version:
            raise ArtifactVersionConflictError(
                f"Epic changed from version {expected_version} to {epic.version}. Reload it."
            )
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._recorder.require_member(requirement_id, actor)
            if self._epics.get_by_requirement_id(requirement_id) != epic:
                raise ArtifactVersionConflictError(
                    "Epic changed before approval could be committed. Reload it."
                )
            approved = epic.approve(
                self._recorder.decision(
                    ApprovalTarget(ApprovalTargetKind.EPIC, epic.id.value),
                    fingerprint,
                    actor,
                    ApprovalDecision.APPROVED,
                    rationale,
                )
            )
            self._epics.save(approved)
        return approved
