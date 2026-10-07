"""Queue automatic knowledge screens and answer suggestions without duplicate work."""

from __future__ import annotations

import uuid

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.domain.entities import ClarificationQuestion
from smb_requirement_agent.application.errors import (
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.corpus_membership import CorpusMembershipPort
from smb_requirement_agent.application.ports.prior_art import PriorArtSchedulerPort
from smb_requirement_agent.application.ports.requirement_knowledge import (
    AnswerSuggestionSchedulerPort,
    KnowledgeReviewPort,
    KnowledgeScreenEnsureOutcome,
    KnowledgeScreenEnsureResult,
    KnowledgeScreenSchedulerPort,
    RequirementKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.use_cases.ai_jobs import command_fingerprint
from smb_requirement_agent.domain.knowledge.errors import RequirementRetiredError
from smb_requirement_agent.jobs.application.ports.ai_jobs import (
    AiJobCommand,
    AiJobRecord,
    AiJobRepositoryPort,
    JsonValue,
)
from smb_requirement_agent.jobs.domain.entities import (
    AiJob,
    AiJobId,
    AiJobOperation,
    AiJobOrigin,
    AiJobStatus,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.errors import (
    DuplicateRequirementStateError,
)
from smb_requirement_agent.requirements.domain.requirement.value_objects import RequirementStatus
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class KnowledgeScreenScheduler(KnowledgeScreenSchedulerPort):
    def __init__(
        self,
        knowledge_review: KnowledgeReviewPort,
        jobs: AiJobRepositoryPort,
        requirements: RequirementRepositoryPort,
        reviews: RequirementKnowledgeRepositoryPort,
        clock: ClockPort,
        automatic_actor: ActorProfile,
        *,
        membership: CorpusMembershipPort | None = None,
        prior_art: PriorArtSchedulerPort | None = None,
    ) -> None:
        self._prior_art = prior_art
        self._knowledge_review = knowledge_review
        self._jobs = jobs
        self._requirements = requirements
        self._reviews = reviews
        self._clock = clock
        self._automatic_actor = automatic_actor
        self._membership = membership

    def _retired(self, requirement_id: RequirementId) -> bool:
        membership = self._membership.get(requirement_id) if self._membership else None
        return membership is not None and membership.retired

    def schedule(self, requirement_id: RequirementId) -> None:
        triggering_requirement = self._requirements.get(requirement_id)
        if triggering_requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        affected = {requirement_id}
        for finding in self._reviews.list_related_findings(requirement_id):
            affected.add(finding.subject_requirement_id)
            affected.add(finding.related_requirement_id)
        for affected_id in sorted(affected, key=lambda value: value.value):
            requirement = self._requirements.get(affected_id)
            if (
                requirement is not None
                and requirement.status is not RequirementStatus.DUPLICATE
                and not self._retired(affected_id)
            ):
                self._schedule_one(
                    affected_id,
                    trigger=(
                        triggering_requirement if affected_id != triggering_requirement.id else None
                    ),
                )
        # Prior art follows the Requirement that changed, never the ones related to it.
        if self._prior_art is not None and not self._retired(requirement_id):
            self._prior_art.schedule(requirement_id)

    def ensure(self, requirement_id: RequirementId) -> KnowledgeScreenEnsureResult:
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        if requirement.status is RequirementStatus.DUPLICATE:
            raise DuplicateRequirementStateError(
                "A duplicate Requirement cannot start a new knowledge screen."
            )
        if self._retired(requirement_id):
            raise RequirementRetiredError(
                "This Requirement is retired from the knowledge corpus, so it is not screened."
            )
        result = self._schedule_one(requirement_id)
        # Opening the Knowledge step checks prior art too, even when the screen is current.
        if self._prior_art is not None:
            self._prior_art.ensure(requirement_id)
        return result

    def _schedule_one(
        self,
        requirement_id: RequirementId,
        *,
        trigger: Requirement | None = None,
    ) -> KnowledgeScreenEnsureResult:
        review = self._knowledge_review.execute(requirement_id)
        if review.current:
            return KnowledgeScreenEnsureResult(KnowledgeScreenEnsureOutcome.CURRENT)
        arguments: dict[str, JsonValue] = {"knowledge_fingerprint": review.current_fingerprint}
        if trigger is not None:
            triggering_requirement = self._requirements.get(trigger.id)
            if triggering_requirement is not None:
                arguments["trigger_requirement_id"] = triggering_requirement.id.value
                arguments["trigger_requirement_version"] = triggering_requirement.version.value
        command = AiJobCommand(arguments)
        operation = AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE
        command_hash = command_fingerprint(requirement_id, operation, command)
        now = self._clock.now()
        job_id = AiJobId(str(uuid.uuid4()))
        job = AiJob(
            job_id,
            requirement_id,
            operation,
            AiJobStatus.QUEUED,
            self._automatic_actor.snapshot(),
            now,
            now,
            f"automatic:{requirement_id.value}:{operation.value}:{command_hash}:{job_id.value}",
            command_hash,
            origin=AiJobOrigin.AUTOMATIC,
        )
        reserved, created = self._jobs.reserve_automatic(AiJobRecord(job, command))
        if created:
            return KnowledgeScreenEnsureResult(
                KnowledgeScreenEnsureOutcome.SCHEDULED, reserved.job.id
            )
        if not reserved.job.status.terminal:
            return KnowledgeScreenEnsureResult(
                KnowledgeScreenEnsureOutcome.ALREADY_SCHEDULED, reserved.job.id
            )
        return KnowledgeScreenEnsureResult(
            KnowledgeScreenEnsureOutcome.MANUAL_RETRY_REQUIRED, reserved.job.id
        )


class AnswerSuggestionScheduler(AnswerSuggestionSchedulerPort):
    """Queue one idempotent automatic suggestion job for every active question."""

    def __init__(
        self,
        jobs: AiJobRepositoryPort,
        clock: ClockPort,
        automatic_actor: ActorProfile,
    ) -> None:
        self._jobs = jobs
        self._clock = clock
        self._automatic_actor = automatic_actor

    def schedule(
        self,
        requirement_id: RequirementId,
        questions: tuple[ClarificationQuestion, ...],
    ) -> None:
        for question in questions:
            if not question.is_active:
                continue
            command = AiJobCommand(
                {
                    "question_id": question.id.value,
                    "expected_version": question.version,
                }
            )
            operation = AiJobOperation.SUGGEST_CLARIFICATION_ANSWERS
            command_hash = command_fingerprint(requirement_id, operation, command)
            if self._jobs.find_active_equivalent(requirement_id, command_hash) is not None:
                continue
            now = self._clock.now()
            job_id = AiJobId(str(uuid.uuid4()))
            job = AiJob(
                job_id,
                requirement_id,
                operation,
                AiJobStatus.QUEUED,
                self._automatic_actor.snapshot(),
                now,
                now,
                f"automatic:{requirement_id.value}:{operation.value}:{command_hash}:{job_id.value}",
                command_hash,
                origin=AiJobOrigin.AUTOMATIC,
            )
            self._jobs.add(AiJobRecord(job, command))
