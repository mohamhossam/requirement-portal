"""Explicit human confirmation of a fully resolved analysis."""

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    RequirementAnalysisConflictError,
    RequirementAnalysisNotFoundError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.application.ports.reference_grounding import (
    ReferenceEvidencePort,
    require_analysis_references,
)
from smb_requirement_agent.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_knowledge import KnowledgeReviewPort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementAccessService,
    RequirementPermission,
)
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class ConfirmRequirementAnalysis:
    """Let the Requirement Owner sign off only after uncertainty is resolved."""

    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        analyses: RequirementAnalysisRepositoryPort,
        clock: ClockPort,
        authorization: RequirementAccessService,
        audits: AnalysisAuditRepositoryPort,
        knowledge: KnowledgeReviewPort,
        transactions: TransactionManagerPort,
        references: ReferenceEvidencePort,
    ) -> None:
        self._requirements = requirements
        self._references = references
        self._analyses = analyses
        self._clock = clock
        self._authorization = authorization
        self._audits = audits
        self._knowledge = knowledge
        self._transactions = transactions

    def execute(
        self, requirement_id: RequirementId, actor: ActorProfile, expected_version: int
    ) -> RequirementAnalysis:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            requirement = self._requirements.get(requirement_id)
            if requirement is None:
                raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
            analysis = self._analyses.get_by_requirement_id(requirement_id)
            if analysis is None:
                raise RequirementAnalysisNotFoundError(
                    f"Analysis for requirement {requirement_id.value!r} not found."
                )
            if analysis.version != expected_version:
                raise RequirementAnalysisConflictError(
                    f"Analysis changed from version {expected_version} to {analysis.version}. "
                    "Reload it."
                )
            self._authorization.require(requirement_id, actor, RequirementPermission.OWNER)
            self._knowledge.require_ready(requirement_id)
            require_analysis_references(self._references, analysis)
            has_open_blockers = any(
                item.is_active and item.is_blocker
                for item in self._audits.list_questions(requirement_id)
            )
            source_outcome = (
                requirement.desired_outcome.value
                if requirement.desired_outcome is not None
                else None
            )
            confirmed = analysis.confirm(
                self._clock.now(),
                actor,
                has_open_blockers=has_open_blockers,
                has_effective_outcome=analysis.effective_desired_outcome(source_outcome)
                is not None,
            )
            self._analyses.save(confirmed)
            return confirmed
