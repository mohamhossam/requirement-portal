"""Run one claimed AI job to completion, cancellation or recorded failure."""

from __future__ import annotations

import logging
import uuid

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    ActorNotFoundError,
    AiJobNotFoundError,
    KnowledgeIndexPendingError,
    KnowledgeScreenConflictError,
)
from smb_requirement_agent.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.application.ports.actor_directory import ActorDirectoryPort
from smb_requirement_agent.application.ports.ai_jobs import (
    AiJobRecord,
    AiJobRepositoryPort,
    JsonValue,
)
from smb_requirement_agent.application.ports.external_work import guard_external_work
from smb_requirement_agent.application.ports.notifications import NotificationRepositoryPort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.public_errors import describe_public_error
from smb_requirement_agent.application.use_cases.analysis_collaboration import (
    AnalysisCollaboration,
    ClarificationResolutionInput,
)
from smb_requirement_agent.application.use_cases.analyze_requirement import AnalyzeRequirement
from smb_requirement_agent.application.use_cases.answer_suggestions import (
    SuggestClarificationAnswers,
)
from smb_requirement_agent.application.use_cases.breakdown_review import (
    GenerateBreakdownReview,
    ResolveOpenQuestion,
)
from smb_requirement_agent.application.use_cases.clarify_requirement_analysis import (
    ClarificationAnswerInput,
    ClarifyRequirementAnalysis,
)
from smb_requirement_agent.application.use_cases.generate_epic import GenerateEpic
from smb_requirement_agent.application.use_cases.generate_features import GenerateFeatures
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.application.use_cases.identity_access import RequirementAccessService
from smb_requirement_agent.application.use_cases.job_execution_context import (
    bind_attempt,
)
from smb_requirement_agent.application.use_cases.prior_art import (
    PriorArtBudgetSpentError,
    ScreenPriorArt,
)
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    ScreenRequirementKnowledge,
)
from smb_requirement_agent.application.use_cases.story_change_proposals import StoryChangeProposals
from smb_requirement_agent.application.use_cases.story_quality import EvaluateFeatureStories
from smb_requirement_agent.application.use_cases.story_workflow import (
    GenerateStories,
    RegenerateStory,
)
from smb_requirement_agent.domain.analysis.value_objects import ClarificationKind, QuestionId
from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.jobs.entities import (
    ActorNotification,
    AiJob,
    AiJobFailure,
    AiJobId,
    AiJobOperation,
    AiJobOrigin,
    AiJobResultResource,
    AiJobStatus,
    NotificationId,
    NotificationKind,
)
from smb_requirement_agent.domain.jobs.errors import AiJobConflictError
from smb_requirement_agent.domain.review.entities import FlagId
from smb_requirement_agent.domain.shared.actors import (
    ActorId,
    ActorProfile,
)
from smb_requirement_agent.domain.story.entities import StoryChangeOperation
from smb_requirement_agent.domain.story.value_objects import StoryId

logger = logging.getLogger("smb_requirement_agent.ai_jobs")


class _CancellationRequested(Exception):
    pass


class _LeaseLost(Exception):
    """Internal control flow: this worker no longer owns the execution attempt."""


class ExecuteAiJob:
    """Dispatch one claimed job through existing application use cases."""

    def __init__(
        self,
        jobs: AiJobRepositoryPort,
        notifications: NotificationRepositoryPort,
        actors: ActorDirectoryPort,
        clock: ClockPort,
        transactions: TransactionManagerPort,
        analyze: AnalyzeRequirement,
        clarify: ClarifyRequirementAnalysis,
        collaboration: AnalysisCollaboration,
        generate_epic: GenerateEpic,
        generate_features: GenerateFeatures,
        generate_stories: GenerateStories,
        regenerate_story: RegenerateStory,
        proposals: StoryChangeProposals,
        quality: EvaluateFeatureStories,
        generate_review: GenerateBreakdownReview,
        resolve_review_question: ResolveOpenQuestion,
        screen_knowledge: ScreenRequirementKnowledge,
        suggest_answers: SuggestClarificationAnswers,
        access: AccessRepositoryPort,
        authorizer: RequirementAccessService,
        generation_context: GenerationContextTokens,
        *,
        screen_prior_art: ScreenPriorArt | None = None,
    ) -> None:
        self._jobs = jobs
        self._notifications = notifications
        self._actors = actors
        self._clock = clock
        self._transactions = transactions
        self._analyze = analyze
        self._clarify = clarify
        self._collaboration = collaboration
        self._generate_epic = generate_epic
        self._generate_features = generate_features
        self._generate_stories = generate_stories
        self._regenerate_story = regenerate_story
        self._proposals = proposals
        self._quality = quality
        self._generate_review = generate_review
        self._resolve_review_question = resolve_review_question
        self._screen_knowledge = screen_knowledge
        self._suggest_answers = suggest_answers
        self._access = access
        self._authorizer = authorizer
        self._generation_context = generation_context
        self._screen_prior_art = screen_prior_art

    def execute(self, record: AiJobRecord) -> AiJob:
        with (
            bind_attempt(record),
            guard_external_work(lambda: self._require_commit_context(record)),
        ):
            return self._execute_attempt(record)

    def _require_commit_context(self, record: AiJobRecord) -> None:
        self._transactions.lock_requirement(record.job.requirement_id)
        self._require_membership(record)
        self._require_generation_context(record)
        current = self._jobs.get(record.job.id)
        if current is None or (
            current.worker_id != record.worker_id or current.attempt_token != record.attempt_token
        ):
            raise _LeaseLost("AI job attempt changed during external work.")
        if current.job.status is AiJobStatus.CANCELLATION_REQUESTED:
            raise _CancellationRequested

    def _execute_attempt(self, record: AiJobRecord) -> AiJob:
        if record.worker_id is None or record.attempt_token is None:
            raise _LeaseLost("AI job execution requires a claimed attempt token.")
        try:
            current = self._require(record.job.id)
            if current.status is AiJobStatus.CANCELLATION_REQUESTED:
                return self._finish_cancel(record, current)
            with self._transactions.transaction():
                self._transactions.lock_requirement(record.job.requirement_id)
                self._require_membership(record)
                self._require_generation_context(record)
                resources = self._dispatch(record)
                self._transactions.lock_requirement(record.job.requirement_id)
                self._require_membership(record)
                current = self._require(record.job.id)
                if current.status is AiJobStatus.CANCELLATION_REQUESTED:
                    raise _CancellationRequested
                now = self._clock.now()
                completed = current.succeed(resources, now)
                if not self._jobs.save_fenced(
                    completed,
                    record.worker_id,
                    record.attempt_token,
                    now,
                ):
                    raise _LeaseLost("AI job lease was lost before completion.")
                self._notify(completed, succeeded=True)
                return completed
        except _CancellationRequested:
            return self._finish_cancel(record, self._require(record.job.id))
        except _LeaseLost:
            raise
        except (KnowledgeIndexPendingError, KnowledgeScreenConflictError) as exc:
            if record.job.operation.requires_current_index:
                return self._defer(record)
            return self._fail(record, exc)
        except PriorArtBudgetSpentError:
            # Not a failure: this hour's judge calls are spent, so the check waits its turn.
            return self._defer(record)
        except Exception as exc:
            return self._fail(record, exc)

    def _fail(self, record: AiJobRecord, exc: Exception) -> AiJob:
        failure = _failure(exc)
        logger.error(
            "AI job %s (%s) failed [correlation_id=%s]",
            record.job.id.value,
            record.job.operation.value,
            failure.correlation_id,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return self._finish_failure(record, failure)

    def _require_membership(self, record: AiJobRecord) -> None:
        if record.job.origin is AiJobOrigin.AUTOMATIC:
            self._authorizer.require_automatic_job_execution(record.job.requirement_id)
            return
        self._authorizer.require_requirement_member_id(
            record.job.requirement_id, record.job.created_by.id
        )

    def _require_generation_context(self, record: AiJobRecord) -> None:
        self._generation_context.require_operation(
            record.job.requirement_id,
            record.job.operation,
            record.command.arguments,
        )

    def _dispatch(self, record: AiJobRecord) -> tuple[AiJobResultResource, ...]:
        job = record.job
        args = record.command.arguments
        requirement_id = job.requirement_id
        actor = self._actor(job.created_by.id)
        base = f"/requirements/{requirement_id.value}"
        operation = job.operation
        if operation is AiJobOperation.ANALYSE_REQUIREMENT:
            self._analyze.execute_workspace(
                actor, requirement_id, force=_bool(args, "force", False)
            )
            return (AiJobResultResource("analysis", f"{base}/clarify"),)
        if operation is AiJobOperation.CLARIFY_REQUIREMENT_ANALYSIS:
            raw_answers = _list(args, "answers")
            answers = tuple(
                ClarificationAnswerInput(
                    ClarificationKind(_string(item, "kind")),
                    _string(item, "subject"),
                    _string(item, "answer"),
                )
                for item in (_object(value) for value in raw_answers)
            )
            self._clarify.execute(
                requirement_id,
                answers,
                _integer(args, "expected_analysis_version"),
                actor,
            )
            return (AiJobResultResource("analysis", f"{base}/clarify"),)
        if operation is AiJobOperation.RESOLVE_CLARIFICATION_QUESTION:
            self._collaboration.resolve(
                requirement_id,
                QuestionId(_string(args, "question_id")),
                _optional_string(args, "answer"),
                _integer(args, "expected_version"),
                actor,
                source_suggestion_id=_optional_string(args, "source_suggestion_id"),
            )
            return (AiJobResultResource("analysis", f"{base}/clarify"),)
        if operation is AiJobOperation.RESOLVE_CLARIFICATION_QUESTIONS:
            raw_answers = _list(args, "answers")
            resolutions = tuple(
                ClarificationResolutionInput(
                    QuestionId(_string(item, "question_id")),
                    _string(item, "answer"),
                    _integer(item, "expected_version"),
                    _optional_string(item, "source_suggestion_id"),
                )
                for item in (_object(value) for value in raw_answers)
            )
            self._collaboration.resolve_batch(requirement_id, resolutions, actor)
            return (AiJobResultResource("analysis", f"{base}/clarify"),)
        if operation is AiJobOperation.GENERATE_EPIC:
            self._generate_epic.execute(actor, requirement_id, force=_bool(args, "force", False))
            return (AiJobResultResource("epic", f"{base}/breakdown/epic"),)
        if operation is AiJobOperation.GENERATE_FEATURES:
            self._generate_features.execute(
                actor, requirement_id, force=_bool(args, "force", False)
            )
            return (AiJobResultResource("features", f"{base}/breakdown"),)
        feature_id = FeatureId(_string(args, "feature_id")) if "feature_id" in args else None
        if operation is AiJobOperation.GENERATE_STORIES and feature_id is not None:
            self._generate_stories.execute(actor, requirement_id, feature_id)
            return (
                AiJobResultResource("stories", f"{base}/breakdown/features/{feature_id.value}"),
            )
        if operation is AiJobOperation.REGENERATE_STORY and feature_id is not None:
            self._regenerate_story.execute_one(
                actor,
                requirement_id,
                feature_id,
                StoryId(_string(args, "story_id")),
                force=_bool(args, "force", False),
            )
            return (
                AiJobResultResource("stories", f"{base}/breakdown/features/{feature_id.value}"),
            )
        if operation is AiJobOperation.REGENERATE_STORY_SET and feature_id is not None:
            self._regenerate_story.execute_all(
                actor, requirement_id, feature_id, force=_bool(args, "force", False)
            )
            return (
                AiJobResultResource("stories", f"{base}/breakdown/features/{feature_id.value}"),
            )
        if operation is AiJobOperation.PROPOSE_STORY_CHANGE and feature_id is not None:
            self._proposals.create(
                actor,
                requirement_id,
                feature_id,
                StoryChangeOperation(_string(args, "change_operation")),
                tuple(StoryId(str(value)) for value in _list(args, "source_story_ids")),
            )
            return (
                AiJobResultResource(
                    "story_proposals",
                    f"{base}/breakdown/features/{feature_id.value}",
                ),
            )
        if operation is AiJobOperation.EVALUATE_FEATURE_QUALITY and feature_id is not None:
            self._quality.execute(actor, requirement_id, feature_id)
            return (
                AiJobResultResource(
                    "story_quality",
                    f"{base}/breakdown/features/{feature_id.value}",
                ),
            )
        if operation is AiJobOperation.GENERATE_BREAKDOWN_REVIEW:
            self._generate_review.execute(actor, requirement_id)
            return (AiJobResultResource("breakdown_review", f"{base}/review"),)
        if operation is AiJobOperation.RESOLVE_REVIEW_OPEN_QUESTION:
            self._resolve_review_question.execute(
                requirement_id,
                FlagId(_string(args, "flag_id")),
                _string(args, "answer"),
                _string(args, "expected_fingerprint"),
                _integer(args, "expected_version"),
                actor,
            )
            return (
                AiJobResultResource("breakdown_review", f"{base}/review"),
                AiJobResultResource("analysis", f"{base}/clarify"),
            )
        if operation is AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE:
            if job.origin is AiJobOrigin.AUTOMATIC:
                review = self._screen_knowledge.execute_automatic(
                    requirement_id,
                    _string(args, "knowledge_fingerprint"),
                )
            else:
                review = self._screen_knowledge.execute(
                    actor,
                    requirement_id,
                    _string(args, "knowledge_fingerprint"),
                )
            recipients: set[ActorId] = set()
            for finding in review.findings:
                if finding.kind.value != "possible_contradiction" or not finding.actionable:
                    continue
                for linked_id in (
                    finding.subject_requirement_id,
                    finding.related_requirement_id,
                ):
                    access = self._access.get_requirement(linked_id)
                    if access is not None and access.owner is not None:
                        recipients.add(access.owner.actor.id)
            for recipient in recipients:
                self._notifications.add(
                    ActorNotification(
                        NotificationId(str(uuid.uuid4())),
                        recipient,
                        job.id,
                        NotificationKind.KNOWLEDGE_CONFLICT_ACTION_REQUIRED,
                        "A possible requirement contradiction needs both owners' review.",
                        self._clock.now(),
                        f"{base}/knowledge",
                    )
                )
            return (AiJobResultResource("knowledge_review", f"{base}/knowledge"),)
        if operation is AiJobOperation.SUGGEST_CLARIFICATION_ANSWERS:
            question_id = QuestionId(_string(args, "question_id"))
            expected_version = _integer(args, "expected_version")
            if job.origin is AiJobOrigin.AUTOMATIC:
                generated = self._suggest_answers.execute_automatic(
                    requirement_id, question_id, expected_version
                )
                if generated is None:
                    return ()
            else:
                self._suggest_answers.execute(requirement_id, question_id, expected_version, actor)
            return (AiJobResultResource("answer_suggestions", f"{base}/clarify"),)
        if operation is AiJobOperation.SCREEN_PRIOR_ART and self._screen_prior_art is not None:
            key = _string(args, "prior_art_key")
            if job.origin is AiJobOrigin.AUTOMATIC:
                self._screen_prior_art.execute_automatic(requirement_id, key)
            else:
                self._screen_prior_art.execute(actor, requirement_id, key)
            return (AiJobResultResource("prior_art", f"{base}/knowledge"),)
        raise AiJobConflictError(f"Unsupported AI job operation {operation.value!r}.")

    def _finish_cancel(self, record: AiJobRecord, job: AiJob) -> AiJob:
        with self._transactions.transaction():
            self._transactions.lock_requirement(record.job.requirement_id)
            current = self._require(job.id)
            if current.status is AiJobStatus.CANCELLED:
                return current
            now = self._clock.now()
            cancelled = current.cancel(now)
            if not self._jobs.save_fenced(
                cancelled,
                record.worker_id or "",
                record.attempt_token or "",
                now,
            ):
                raise _LeaseLost("AI job lease was lost before cancellation acknowledgement.")
            return cancelled

    def _defer(self, record: AiJobRecord) -> AiJob:
        """The index gate is checked before claiming, so a source can change in between.

        Waiting for the index is not a failure: return the attempt to the queue
        unconsumed and let the gate hold it until the index is current.
        """
        with self._transactions.transaction():
            self._transactions.lock_requirement(record.job.requirement_id)
            current = self._require(record.job.id)
            if current.status is AiJobStatus.CANCELLATION_REQUESTED:
                return self._finish_cancel(record, current)
            now = self._clock.now()
            deferred = current.defer(now)
            if not self._jobs.save_fenced(
                deferred,
                record.worker_id or "",
                record.attempt_token or "",
                now,
            ):
                raise _LeaseLost("AI job lease was lost before it could be requeued.")
            logger.info(
                "AI job %s (%s) requeued to wait for the index or its hourly budget",
                record.job.id.value,
                record.job.operation.value,
            )
            return deferred

    def _finish_failure(self, record: AiJobRecord, failure: AiJobFailure) -> AiJob:
        with self._transactions.transaction():
            self._transactions.lock_requirement(record.job.requirement_id)
            current = self._require(record.job.id)
            if current.status is AiJobStatus.CANCELLATION_REQUESTED:
                return self._finish_cancel(record, current)
            now = self._clock.now()
            failed = current.fail(failure, now)
            if not self._jobs.save_fenced(
                failed,
                record.worker_id or "",
                record.attempt_token or "",
                now,
            ):
                raise _LeaseLost("AI job lease was lost before failure was recorded.")
            self._notify(failed, succeeded=False)
            return failed

    def _notify(self, job: AiJob, *, succeeded: bool) -> None:
        if job.origin is AiJobOrigin.AUTOMATIC and succeeded:
            return
        recipient_id = job.created_by.id
        if job.origin is AiJobOrigin.AUTOMATIC:
            access = self._access.get_requirement(job.requirement_id)
            if access is None or access.owner is None:
                return
            recipient_id = access.owner.actor.id
        kind = NotificationKind.AI_JOB_SUCCEEDED if succeeded else NotificationKind.AI_JOB_FAILED
        message = (
            f"{job.operation.value.replace('_', ' ').capitalize()} completed."
            if succeeded
            else f"{job.operation.value.replace('_', ' ').capitalize()} failed."
        )
        resource = job.result_resources[0].path if job.result_resources else None
        self._notifications.add(
            ActorNotification(
                NotificationId(str(uuid.uuid4())),
                recipient_id,
                job.id,
                kind,
                message,
                self._clock.now(),
                resource,
            )
        )

    def _require(self, job_id: AiJobId) -> AiJob:
        record = self._jobs.get(job_id)
        if record is None:
            raise AiJobNotFoundError(f"AI job {job_id.value!r} not found.")
        return record.job

    def _actor(self, actor_id: ActorId) -> ActorProfile:
        actor = self._actors.get(actor_id)
        if actor is None and actor_id.value == "system:requirement-knowledge":
            return ActorProfile(actor_id, "Automatic requirement knowledge")
        if actor is None:
            raise ActorNotFoundError(f"Actor {actor_id.value!r} is not known to this workspace.")
        return actor


def _failure(exc: Exception) -> AiJobFailure:
    public = describe_public_error(exc)
    return AiJobFailure(
        public.code,
        public.message,
        public.retryable,
        str(uuid.uuid4()),
    )


def _object(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise AiJobConflictError("AI job command contains an invalid object.")
    return value


def _string(values: dict[str, JsonValue], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AiJobConflictError(f"AI job command requires {key}.")
    return value.strip()


def _optional_string(values: dict[str, JsonValue], key: str) -> str | None:
    value = values.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise AiJobConflictError(f"AI job command {key} must be text or null.")
    return value


def _integer(values: dict[str, JsonValue], key: str) -> int:
    value = values.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise AiJobConflictError(f"AI job command {key} must be an integer.")
    return value


def _bool(values: dict[str, JsonValue], key: str, default: bool) -> bool:
    value = values.get(key, default)
    if not isinstance(value, bool):
        raise AiJobConflictError(f"AI job command {key} must be a boolean.")
    return value


def _list(values: dict[str, JsonValue], key: str) -> list[JsonValue]:
    value = values.get(key)
    if not isinstance(value, list):
        raise AiJobConflictError(f"AI job command {key} must be a list.")
    return value
