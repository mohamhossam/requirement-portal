"""Queue, control, execute, and notify durable model-backed operations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    AiJobNotFoundError,
    NotificationNotFoundError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.application.use_cases.identity_access import RequirementAccessService
from smb_requirement_agent.jobs.application.ports.ai_jobs import (
    AiJobCommand,
    AiJobRecord,
    AiJobRepositoryPort,
)
from smb_requirement_agent.jobs.application.ports.notifications import NotificationRepositoryPort
from smb_requirement_agent.jobs.application.use_cases.command_fingerprint import command_fingerprint
from smb_requirement_agent.jobs.application.use_cases.job_execution_context import (
    current_attempt,
)
from smb_requirement_agent.jobs.domain.entities import (
    ActorNotification,
    AiJob,
    AiJobId,
    AiJobOperation,
    AiJobOrigin,
    AiJobStatus,
    NotificationId,
    NotificationPreference,
)
from smb_requirement_agent.jobs.domain.errors import AiJobConflictError
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True)
class StartAiJobResult:
    job: AiJob
    created: bool


# Job and notification lists are polled, so they are bounded (ADR-0079).
DEFAULT_LIST_LIMIT = 100
MAX_LIST_LIMIT = 500


class AnalysisProgressReporter:
    """Persist progress for the active asynchronous analysis job, if one exists."""

    def __init__(self, jobs: AiJobRepositoryPort, clock: ClockPort) -> None:
        self._jobs = jobs
        self._clock = clock

    def report(
        self,
        requirement_id: RequirementId,
        phase: str,
        completed_units: int,
        total_units: int,
        current_section_label: str | None,
    ) -> None:
        attempt = current_attempt()
        if attempt is None or attempt.job.requirement_id != requirement_id:
            return
        active = self._jobs.get(attempt.job.id)
        if (
            active is not None
            and active.job.status is AiJobStatus.RUNNING
            and attempt.worker_id
            and attempt.attempt_token
            and active.worker_id == attempt.worker_id
            and active.attempt_token == attempt.attempt_token
        ):
            now = self._clock.now()
            self._jobs.report_progress_fenced(
                active.job.report_progress(
                    phase,
                    completed_units,
                    total_units,
                    current_section_label,
                    now,
                ),
                attempt.worker_id,
                attempt.attempt_token,
                now,
            )


class AiJobs:
    def __init__(
        self,
        jobs: AiJobRepositoryPort,
        requirements: RequirementRepositoryPort,
        authorizer: RequirementAccessService,
        clock: ClockPort,
        generation_context: GenerationContextTokens,
        transactions: TransactionManagerPort,
    ) -> None:
        self._jobs = jobs
        self._requirements = requirements
        self._authorizer = authorizer
        self._clock = clock
        self._generation_context = generation_context
        self._transactions = transactions

    def start(
        self,
        requirement_id: RequirementId,
        operation: AiJobOperation,
        command: AiJobCommand,
        idempotency_key: str,
        actor: ActorProfile,
    ) -> StartAiJobResult:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            return self._start(requirement_id, operation, command, idempotency_key, actor)

    def _start(
        self,
        requirement_id: RequirementId,
        operation: AiJobOperation,
        command: AiJobCommand,
        idempotency_key: str,
        actor: ActorProfile,
    ) -> StartAiJobResult:
        if self._requirements.get(requirement_id) is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        self._authorizer.require_requirement_member(requirement_id, actor)
        key = idempotency_key.strip()
        if not key or len(key) > 200:
            raise AiJobConflictError("Idempotency-Key must contain 1 to 200 characters.")
        fingerprint = command_fingerprint(requirement_id, operation, command)
        existing = self._jobs.get_by_idempotency(actor.id, key)
        if existing is not None:
            if (
                existing.job.requirement_id != requirement_id
                or existing.job.command_fingerprint != fingerprint
            ):
                raise AiJobConflictError(
                    "The Idempotency-Key was already used for different AI job input."
                )
            return StartAiJobResult(existing.job, False)
        self._generation_context.require_operation(requirement_id, operation, command.arguments)
        equivalent = self._jobs.find_active_equivalent(requirement_id, fingerprint)
        if equivalent is not None:
            self._jobs.bind_idempotency(equivalent.job.id, actor.id, key, fingerprint)
            return StartAiJobResult(equivalent.job, False)
        now = self._clock.now()
        job = AiJob(
            AiJobId(str(uuid.uuid4())),
            requirement_id,
            operation,
            AiJobStatus.QUEUED,
            actor.snapshot(),
            now,
            now,
            key,
            fingerprint,
        )
        self._jobs.add(AiJobRecord(job, command))
        return StartAiJobResult(job, True)

    def start_automatic(
        self,
        requirement_id: RequirementId,
        operation: AiJobOperation,
        command: AiJobCommand,
        actor: ActorProfile,
    ) -> StartAiJobResult:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            return self._start_automatic(requirement_id, operation, command, actor)

    def _start_automatic(
        self,
        requirement_id: RequirementId,
        operation: AiJobOperation,
        command: AiJobCommand,
        actor: ActorProfile,
    ) -> StartAiJobResult:
        """Schedule idempotent system-initiated work without impersonating a user action."""
        fingerprint = command_fingerprint(requirement_id, operation, command)
        existing = self._jobs.find_active_equivalent(requirement_id, fingerprint)
        if existing is not None:
            return StartAiJobResult(existing.job, False)
        now = self._clock.now()
        job = AiJob(
            AiJobId(str(uuid.uuid4())),
            requirement_id,
            operation,
            AiJobStatus.QUEUED,
            actor.snapshot(),
            now,
            now,
            f"automatic:{operation.value}:{fingerprint}",
            fingerprint,
            origin=AiJobOrigin.AUTOMATIC,
        )
        self._jobs.add(AiJobRecord(job, command))
        return StartAiJobResult(job, True)

    def get(self, requirement_id: RequirementId, job_id: AiJobId) -> AiJob:
        record = self._require(job_id)
        if record.job.requirement_id != requirement_id:
            raise AiJobNotFoundError(f"AI job {job_id.value!r} not found.")
        return record.job

    def command(self, requirement_id: RequirementId, job_id: AiJobId) -> AiJobCommand:
        record = self._require(job_id)
        if record.job.requirement_id != requirement_id:
            raise AiJobNotFoundError(f"AI job {job_id.value!r} not found.")
        return record.command

    def list(
        self,
        requirement_id: RequirementId,
        *,
        active_only: bool = False,
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> list[AiJobRecord]:
        """Every active job, then the newest finished ones, `limit` in all.

        A Requirement's history only grows, and the browser polls this list
        while work runs, so it is bounded; active jobs are never cut off, so
        nothing being watched can drop out. Records, not bare jobs: the caller
        needs each command too, and reading it again per job would cost one
        query per row on every poll.
        """
        if self._requirements.get(requirement_id) is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        active = self._jobs.list_for_requirement(requirement_id, active_only=True)
        if active_only:
            return list(active)
        recent = self._jobs.list_for_requirement(requirement_id, limit=limit)
        merged = {item.job.id: item for item in (*recent, *active)}
        newest = sorted(merged.values(), key=lambda item: item.job.created_at, reverse=True)
        room = max(limit - len(active), 0)
        finished = [item for item in newest if item.job.status.terminal][:room]
        kept = {item.job.id for item in (*active, *finished)}
        return [item for item in newest if item.job.id in kept]

    def cancel(
        self,
        requirement_id: RequirementId,
        job_id: AiJobId,
        actor: ActorProfile,
        *,
        expected_version: int,
    ) -> AiJob:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            return self._cancel(requirement_id, job_id, actor, expected_version=expected_version)

    def _cancel(
        self,
        requirement_id: RequirementId,
        job_id: AiJobId,
        actor: ActorProfile,
        *,
        expected_version: int,
    ) -> AiJob:
        record = self._require(job_id)
        self._require_scope_and_control(record.job, requirement_id, actor.id)
        if record.job.version != expected_version:
            raise AiJobConflictError(
                f"AI job changed from version {expected_version} to "
                f"{record.job.version}. Reload it."
            )
        updated = record.job.request_cancellation(self._clock.now())
        if updated is not record.job:
            self._jobs.save(updated)
        return updated

    def retry(
        self,
        requirement_id: RequirementId,
        job_id: AiJobId,
        idempotency_key: str,
        actor: ActorProfile,
        *,
        expected_version: int,
    ) -> StartAiJobResult:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            return self._retry(
                requirement_id,
                job_id,
                idempotency_key,
                actor,
                expected_version=expected_version,
            )

    def _retry(
        self,
        requirement_id: RequirementId,
        job_id: AiJobId,
        idempotency_key: str,
        actor: ActorProfile,
        *,
        expected_version: int,
    ) -> StartAiJobResult:
        record = self._require(job_id)
        self._require_scope_and_control(record.job, requirement_id, actor.id)
        if record.job.version != expected_version:
            raise AiJobConflictError(
                f"AI job changed from version {expected_version} to "
                f"{record.job.version}. Reload it."
            )
        if record.job.status is AiJobStatus.FAILED:
            if record.job.failure is None or not record.job.failure.retryable:
                raise AiJobConflictError("This AI job failure requires a new action, not a retry.")
        elif record.job.status is not AiJobStatus.CANCELLED and not (
            record.job.status is AiJobStatus.SUCCEEDED
            and record.job.operation is AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE
        ):
            raise AiJobConflictError("Only failed or cancelled AI jobs can be retried.")
        result = self.start(
            requirement_id, record.job.operation, record.command, idempotency_key, actor
        )
        if result.created:
            retried = replace(
                result.job,
                retry_of_job_id=record.job.id,
                version=result.job.version + 1,
            )
            self._jobs.save(retried)
            return StartAiJobResult(retried, True)
        return result

    def _require(self, job_id: AiJobId) -> AiJobRecord:
        record = self._jobs.get(job_id)
        if record is None:
            raise AiJobNotFoundError(f"AI job {job_id.value!r} not found.")
        return record

    def _require_scope_and_control(
        self, job: AiJob, requirement_id: RequirementId, actor_id: ActorId
    ) -> None:
        if job.requirement_id != requirement_id:
            raise AiJobNotFoundError(f"AI job {job.id.value!r} not found.")
        self._authorizer.require_job_controller(
            requirement_id,
            actor_id,
            job.created_by.id,
            automatic=job.origin is AiJobOrigin.AUTOMATIC,
        )


class Notifications:
    def __init__(self, repository: NotificationRepositoryPort, clock: ClockPort) -> None:
        self._repository = repository
        self._clock = clock

    def list(
        self, actor_id: ActorId, *, unread_only: bool = False, limit: int = DEFAULT_LIST_LIMIT
    ) -> list[ActorNotification]:
        """The newest notifications, polled by every open tab, so bounded."""
        return self._repository.list_for_actor(actor_id, unread_only=unread_only, limit=limit)

    def mark_read(self, notification_id: NotificationId, actor_id: ActorId) -> ActorNotification:
        notification = self._repository.get(notification_id)
        if notification is None or notification.recipient_id != actor_id:
            raise NotificationNotFoundError(f"Notification {notification_id.value!r} not found.")
        updated = notification.mark_read(self._clock.now())
        self._repository.save(updated)
        return updated

    def preference(self, actor_id: ActorId) -> NotificationPreference:
        return self._repository.get_preference(actor_id)

    def set_preference(self, actor_id: ActorId, browser_enabled: bool) -> NotificationPreference:
        preference = NotificationPreference(actor_id, browser_enabled)
        self._repository.save_preference(preference)
        return preference
