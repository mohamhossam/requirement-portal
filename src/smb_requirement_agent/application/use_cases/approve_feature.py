"""ApproveFeature use case: a human sign-off on one Feature's current content.

Governance's, beside `approve_epic`; it moved out of breakdown's `feature_review` in ADR-0103 PR 11.
"""

from __future__ import annotations

from smb_requirement_agent.application.errors import (
    ApprovalWorkflowNotReadyError,
    ArtifactVersionConflictError,
)
from smb_requirement_agent.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.application.ports.feature_repository import FeatureRepositoryPort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.approval_workflow import ApprovalRecorder
from smb_requirement_agent.application.use_cases.feature_review import FeatureLookup
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.review.fingerprints import artifact_fingerprint
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


class ApproveFeature(FeatureLookup):
    """Records a human sign-off on one Feature's current content."""

    def __init__(
        self,
        requirement_repository: RequirementRepositoryPort,
        epic_repository: EpicRepositoryPort,
        feature_repository: FeatureRepositoryPort,
        recorder: ApprovalRecorder,
        transactions: TransactionManagerPort,
    ) -> None:
        super().__init__(requirement_repository, epic_repository, feature_repository)
        self._recorder = recorder
        self._transactions = transactions

    def execute(
        self,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        actor: ActorProfile,
        expected_version: int,
        expected_fingerprint: str,
        rationale: str | None = None,
    ) -> Feature:
        feature = self._feature(requirement_id, feature_id)
        self._recorder.require_member(requirement_id, actor)
        fingerprint = artifact_fingerprint(feature)
        if expected_fingerprint.strip() != fingerprint:
            raise ApprovalWorkflowNotReadyError(
                "The Feature changed. Reload it before approving the current content."
            )
        if feature.current_approval(fingerprint) is not None:
            return feature
        if feature.version != expected_version:
            raise ArtifactVersionConflictError(
                f"Feature changed from version {expected_version} to {feature.version}. Reload it."
            )
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            if self._feature(requirement_id, feature_id) != feature:
                raise ArtifactVersionConflictError(
                    "Feature changed before approval could be committed. Reload it."
                )
            approved = feature.approve(
                self._recorder.decision(
                    ApprovalTarget(ApprovalTargetKind.FEATURE, feature.id.value),
                    fingerprint,
                    actor,
                    ApprovalDecision.APPROVED,
                    rationale,
                )
            )
            self._features.save(approved)
        return approved
