"""Provider-neutral durable AI jobs and actor notifications."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from smb_requirement_agent.domain.jobs.errors import AiJobConflictError, InvalidAiJobError
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorSnapshot,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.staleness import require_aware


def _text(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise InvalidAiJobError(f"AI job {field} must not be blank.")
    return cleaned


@dataclass(frozen=True, order=True)
class AiJobId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "id"))


class AiJobOperation(StrEnum):
    ANALYSE_REQUIREMENT = "analyse_requirement"
    CLARIFY_REQUIREMENT_ANALYSIS = "clarify_requirement_analysis"
    RESOLVE_CLARIFICATION_QUESTION = "resolve_clarification_question"
    RESOLVE_CLARIFICATION_QUESTIONS = "resolve_clarification_questions"
    GENERATE_EPIC = "generate_epic"
    GENERATE_FEATURES = "generate_features"
    GENERATE_STORIES = "generate_stories"
    REGENERATE_STORY = "regenerate_story"
    REGENERATE_STORY_SET = "regenerate_story_set"
    PROPOSE_STORY_CHANGE = "propose_story_change"
    EVALUATE_FEATURE_QUALITY = "evaluate_feature_quality"
    GENERATE_BREAKDOWN_REVIEW = "generate_breakdown_review"
    RESOLVE_REVIEW_OPEN_QUESTION = "resolve_review_open_question"
    SCREEN_REQUIREMENT_KNOWLEDGE = "screen_requirement_knowledge"
    SUGGEST_CLARIFICATION_ANSWERS = "suggest_clarification_answers"
    # Prior art from historic requirements (Knowledge Center E2). Automatic, informational,
    # and claimed only when nothing else is waiting.
    SCREEN_PRIOR_ART = "screen_prior_art"

    @property
    def uses_analyzer(self) -> bool:
        return self in {
            self.ANALYSE_REQUIREMENT,
            self.CLARIFY_REQUIREMENT_ANALYSIS,
            self.RESOLVE_CLARIFICATION_QUESTION,
            self.RESOLVE_CLARIFICATION_QUESTIONS,
            self.RESOLVE_REVIEW_OPEN_QUESTION,
        }

    @property
    def requires_current_index(self) -> bool:
        """Operations that wait for the Requirement knowledge index instead of failing."""
        return self in {self.SCREEN_REQUIREMENT_KNOWLEDGE, self.SUGGEST_CLARIFICATION_ANSWERS}


class AiJobOrigin(StrEnum):
    USER = "user"
    AUTOMATIC = "automatic"


class AiJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLATION_REQUESTED = "cancellation_requested"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    @property
    def terminal(self) -> bool:
        return self in {self.CANCELLED, self.SUCCEEDED, self.FAILED}

    @property
    def holds_attempt(self) -> bool:
        """Only these states own a worker lease and attempt token."""
        return self in {self.RUNNING, self.CANCELLATION_REQUESTED}


@dataclass(frozen=True)
class AiJobFailure:
    code: str
    message: str
    retryable: bool
    correlation_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _text(self.code, "failure code"))
        object.__setattr__(self, "message", _text(self.message, "failure message"))
        object.__setattr__(
            self, "correlation_id", _text(self.correlation_id, "failure correlation id")
        )


@dataclass(frozen=True)
class AiJobResultResource:
    kind: str
    path: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _text(self.kind, "result kind"))
        path = _text(self.path, "result path")
        if not path.startswith("/"):
            raise InvalidAiJobError("AI job result paths must be application-relative.")
        object.__setattr__(self, "path", path)


@dataclass(frozen=True)
class AiJob:
    id: AiJobId
    requirement_id: RequirementId
    operation: AiJobOperation
    status: AiJobStatus
    created_by: ActorSnapshot
    created_at: datetime
    updated_at: datetime
    idempotency_key: str
    command_fingerprint: str
    attempt_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    retry_of_job_id: AiJobId | None = None
    failure: AiJobFailure | None = None
    result_resources: tuple[AiJobResultResource, ...] = ()
    origin: AiJobOrigin = AiJobOrigin.USER
    phase: str | None = None
    completed_units: int = 0
    total_units: int | None = None
    current_section_label: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        require_aware(self.created_at, "AI job created_at")
        require_aware(self.updated_at, "AI job updated_at")
        for value, field in (
            (self.started_at, "started_at"),
            (self.completed_at, "completed_at"),
            (self.cancel_requested_at, "cancel_requested_at"),
        ):
            if value is not None:
                require_aware(value, f"AI job {field}")
        object.__setattr__(self, "idempotency_key", _text(self.idempotency_key, "idempotency key"))
        object.__setattr__(
            self, "command_fingerprint", _text(self.command_fingerprint, "command fingerprint")
        )
        if self.attempt_count < 0:
            raise InvalidAiJobError("AI job attempt count cannot be negative.")
        if self.version < 1:
            raise InvalidAiJobError("AI job version must be positive.")
        if self.completed_units < 0 or (
            self.total_units is not None
            and (self.total_units < 0 or self.completed_units > self.total_units)
        ):
            raise InvalidAiJobError("AI job progress units are invalid.")
        if self.phase is not None:
            object.__setattr__(self, "phase", self.phase.strip() or None)
        if self.current_section_label is not None:
            object.__setattr__(
                self, "current_section_label", self.current_section_label.strip() or None
            )

    def claim(self, now: datetime) -> AiJob:
        if self.status is not AiJobStatus.QUEUED:
            raise AiJobConflictError("Only a queued AI job can be claimed.")
        require_aware(now, "AI job claim time")
        return replace(
            self,
            status=AiJobStatus.RUNNING,
            started_at=now,
            updated_at=now,
            attempt_count=self.attempt_count + 1,
            failure=None,
            phase="preparing_analysis" if self.operation.uses_analyzer else "running",
            completed_units=0,
            total_units=None,
            current_section_label=None,
            version=self.version + 1,
        )

    def defer(self, now: datetime) -> AiJob:
        """Return a claimed attempt that could not start to the queue, unconsumed."""
        if self.status is not AiJobStatus.RUNNING:
            raise AiJobConflictError("Only a running AI job can be deferred.")
        require_aware(now, "AI job deferral time")
        attempts = max(0, self.attempt_count - 1)
        return replace(
            self,
            status=AiJobStatus.QUEUED,
            started_at=self.started_at if attempts else None,
            updated_at=now,
            attempt_count=attempts,
            phase=None,
            completed_units=0,
            total_units=None,
            current_section_label=None,
            version=self.version + 1,
        )

    def report_progress(
        self,
        phase: str,
        completed_units: int,
        total_units: int,
        current_section_label: str | None,
        now: datetime,
    ) -> AiJob:
        if self.status is not AiJobStatus.RUNNING:
            raise AiJobConflictError("Only a running AI job can report progress.")
        require_aware(now, "AI job progress time")
        return replace(
            self,
            phase=_text(phase, "progress phase"),
            completed_units=completed_units,
            total_units=total_units,
            current_section_label=current_section_label,
            updated_at=now,
            version=self.version + 1,
        )

    def request_cancellation(self, now: datetime) -> AiJob:
        require_aware(now, "AI job cancellation time")
        if self.status is AiJobStatus.QUEUED:
            return replace(
                self,
                status=AiJobStatus.CANCELLED,
                cancel_requested_at=now,
                completed_at=now,
                updated_at=now,
                version=self.version + 1,
            )
        if self.status is AiJobStatus.RUNNING:
            return replace(
                self,
                status=AiJobStatus.CANCELLATION_REQUESTED,
                cancel_requested_at=now,
                updated_at=now,
                version=self.version + 1,
            )
        if self.status in {AiJobStatus.CANCELLATION_REQUESTED, AiJobStatus.CANCELLED}:
            return self
        raise AiJobConflictError("A completed AI job cannot be cancelled.")

    def cancel(self, now: datetime) -> AiJob:
        if self.status not in {AiJobStatus.RUNNING, AiJobStatus.CANCELLATION_REQUESTED}:
            raise AiJobConflictError("Only a running AI job can finish cancellation.")
        require_aware(now, "AI job cancelled time")
        return replace(
            self,
            status=AiJobStatus.CANCELLED,
            cancel_requested_at=self.cancel_requested_at or now,
            completed_at=now,
            updated_at=now,
            phase="completed",
            completed_units=self.total_units or max(1, self.completed_units),
            total_units=self.total_units or max(1, self.completed_units),
            current_section_label=None,
            version=self.version + 1,
        )

    def succeed(self, resources: tuple[AiJobResultResource, ...], now: datetime) -> AiJob:
        if self.status is not AiJobStatus.RUNNING:
            raise AiJobConflictError("Only a running AI job can succeed.")
        require_aware(now, "AI job completion time")
        return replace(
            self,
            status=AiJobStatus.SUCCEEDED,
            result_resources=resources,
            completed_at=now,
            updated_at=now,
            phase="completed",
            current_section_label=None,
            version=self.version + 1,
        )

    def fail(self, failure: AiJobFailure, now: datetime) -> AiJob:
        if self.status not in {AiJobStatus.RUNNING, AiJobStatus.CANCELLATION_REQUESTED}:
            raise AiJobConflictError("Only an active AI job can fail.")
        require_aware(now, "AI job failure time")
        return replace(
            self,
            status=AiJobStatus.FAILED,
            failure=failure,
            completed_at=now,
            updated_at=now,
            version=self.version + 1,
        )


@dataclass(frozen=True, order=True)
class NotificationId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "notification id"))


class NotificationKind(StrEnum):
    AI_JOB_SUCCEEDED = "ai_job_succeeded"
    AI_JOB_FAILED = "ai_job_failed"
    KNOWLEDGE_CONFLICT_ACTION_REQUIRED = "knowledge_conflict_action_required"
    # A knowledge admin asks the owners to decide a finding (Knowledge Center B2).
    KNOWLEDGE_FINDINGS_NUDGE = "knowledge_findings_nudge"
    # A knowledge admin retires the owner's Requirement from the corpus, or reinstates it (B3).
    KNOWLEDGE_CORPUS_RETIRED = "knowledge_corpus_retired"
    KNOWLEDGE_CORPUS_REINSTATED = "knowledge_corpus_reinstated"


@dataclass(frozen=True)
class ActorNotification:
    id: NotificationId
    recipient_id: ActorId
    # The AI job it reports on; None for a notification no job raised, such as a nudge.
    job_id: AiJobId | None
    kind: NotificationKind
    message: str
    created_at: datetime
    resource_path: str | None = None
    read_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "message", _text(self.message, "notification message"))
        require_aware(self.created_at, "notification created_at")
        if self.read_at is not None:
            require_aware(self.read_at, "notification read_at")

    def mark_read(self, now: datetime) -> ActorNotification:
        require_aware(now, "notification read time")
        return self if self.read_at is not None else replace(self, read_at=now)


@dataclass(frozen=True)
class NotificationPreference:
    actor_id: ActorId
    browser_enabled: bool = False
