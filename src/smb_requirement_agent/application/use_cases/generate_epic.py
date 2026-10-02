"""GenerateEpic use case."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from smb_requirement_agent.application.errors import (
    AnalysisConfirmationRequiredError,
    ArtifactVersionConflictError,
    RequirementAnalysisNotFoundError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.clock import ClockPort
from smb_requirement_agent.application.ports.epic_generator import EpicGeneratorPort
from smb_requirement_agent.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_repository import RequirementRepositoryPort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementAccessService,
    RequirementPermission,
)
from smb_requirement_agent.application.use_cases.invalidate_derived_artifacts import (
    InvalidateDerivedArtifacts,
)
from smb_requirement_agent.application.use_cases.source_lineage import generation_lineage
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.epic.errors import EpicRegenerationConflictError
from smb_requirement_agent.domain.epic.value_objects import (
    BusinessCase,
    BusinessOutcome,
    EpicId,
    EpicName,
    EpicProvenance,
    EpicStatus,
)
from smb_requirement_agent.domain.identity.entities import ActorProfile
from smb_requirement_agent.domain.requirement.value_objects import RequirementId


@dataclass(frozen=True)
class GenerateEpicResult:
    """The generated Epic, and whether it replaced an existing one."""

    epic: Epic
    replaced_existing: bool


class GenerateEpic:
    """Generates an Epic candidate from a requirement and its analysis.

    The analysis is a required input, not optional enrichment: generating from
    raw requirement text alone invites the model to invent the business
    justification that the analysis deliberately surfaces as assumptions and
    open questions.
    """

    def __init__(
        self,
        requirement_repository: RequirementRepositoryPort,
        analysis_repository: RequirementAnalysisRepositoryPort,
        epic_repository: EpicRepositoryPort,
        generator: EpicGeneratorPort,
        clock: ClockPort,
        invalidation: InvalidateDerivedArtifacts,
        transactions: TransactionManagerPort,
        *,
        authorization: RequirementAccessService,
        contexts: GenerationContextTokens,
    ) -> None:
        self._contexts = contexts
        self._requirements = requirement_repository
        self._analyses = analysis_repository
        self._epics = epic_repository
        self._generator = generator
        self._clock = clock
        self._invalidation = invalidation
        self._transactions = transactions
        self._authorization = authorization

    def execute(
        self, actor: ActorProfile, requirement_id: RequirementId, *, force: bool = False
    ) -> GenerateEpicResult:
        with (
            self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER),
            self._contexts.guard(
                lambda: self._contexts.epic(requirement_id), references_for=requirement_id
            ),
        ):
            return self._execute(requirement_id=requirement_id, force=force)

    def _execute(self, requirement_id: RequirementId, *, force: bool = False) -> GenerateEpicResult:
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")

        analysis = self._analyses.get_by_requirement_id(requirement_id)
        if analysis is None:
            raise RequirementAnalysisNotFoundError(
                f"Requirement {requirement_id.value!r} must be analysed before an Epic "
                "can be generated."
            )
        requirement.require_active()
        availability = analysis.epic_generation_availability()
        if not availability.allowed:
            raise AnalysisConfirmationRequiredError(availability.reason)

        existing = self._epics.get_by_requirement_id(requirement_id)
        if existing is not None and existing.is_human_owned and not force:
            raise EpicRegenerationConflictError(
                f"Epic for requirement {requirement_id.value!r} has been "
                f"{existing.status.value} by a human. Regenerate with force to replace it."
            )

        with self._transactions.external_call():
            candidate = self._generator.generate(requirement, analysis)

        epic = Epic(
            source_lineage=generation_lineage(analysis),
            # One Epic per requirement, so the Epic's identity belongs to the
            # requirement rather than to a particular generation of its text.
            # Minting a fresh id on regeneration would orphan anything that
            # references the Epic, such as the Features beneath it.
            id=existing.id if existing is not None else EpicId(str(uuid.uuid4())),
            requirement_id=requirement.id,
            name=EpicName(candidate["name"]),
            outcome=BusinessOutcome(candidate["outcome"]),
            business_case=BusinessCase(candidate["business_case"]),
            status=EpicStatus.GENERATED,
            provenance=EpicProvenance(
                generated_at=self._clock.now(),
                model=candidate["model"],
                prompt_version=candidate["prompt_version"],
            ),
            version=existing.version + 1 if existing is not None else 1,
        )
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            latest_requirement = self._requirements.get(requirement_id)
            latest_analysis = self._analyses.get_by_requirement_id(requirement_id)
            latest_epic = self._epics.get_by_requirement_id(requirement_id)
            if (
                latest_requirement != requirement
                or latest_analysis != analysis
                or latest_epic != existing
            ):
                raise ArtifactVersionConflictError(
                    "Requirement, analysis, or Epic changed while generation was running. "
                    "Reload it."
                )
            self._epics.save(epic)

            if existing is not None:
                self._invalidation.for_changed_epic(epic)

        return GenerateEpicResult(epic=epic, replaced_existing=existing is not None)
