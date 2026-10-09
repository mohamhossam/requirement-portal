"""A job that meets a transient outage waits and runs again (ADR-0020 amendment).

Provider rate limits and outages, and an unreachable platform service, pass on their own.
The job returns to the queue with a backoff instead of failing at once, its retries count
toward the attempt cap, and its Requirement's other jobs wait behind it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import RLock

import pytest

from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobCommand, AiJobRecord
from smb_requirement_agent.jobs.domain.entities import (
    AiJob,
    AiJobFailure,
    AiJobId,
    AiJobOperation,
    AiJobStatus,
)
from smb_requirement_agent.jobs.domain.errors import AiJobConflictError, InvalidAiJobError
from smb_requirement_agent.jobs.infrastructure.in_memory_ai_jobs import InMemoryAiJobStore
from smb_requirement_agent.shared_kernel.actors import ActorId, ActorSnapshot
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.workflows.application.use_cases.ai_job_execution import (
    TRANSIENT_FAILURE_CODES,
    RetryBackoff,
)
from smb_requirement_agent.workflows.infrastructure.polling_worker import metric_status

NOW = datetime(2026, 10, 9, 12, tzinfo=UTC)
LATER = NOW + timedelta(seconds=30)
OWNER = ActorSnapshot(ActorId("actor-1"), "Owner")


def _job(job_id: str, requirement: str, created: datetime = NOW) -> AiJob:
    return AiJob(
        AiJobId(job_id),
        RequirementId(requirement),
        AiJobOperation.ANALYSE_REQUIREMENT,
        AiJobStatus.QUEUED,
        OWNER,
        created,
        created,
        f"key-{job_id}",
        f"fingerprint-{job_id}",
    )


def test_a_requeued_attempt_stays_spent_and_waits() -> None:
    running = _job("job-1", "req-1").claim(NOW)

    waiting = running.requeue(NOW, LATER)

    assert waiting.status is AiJobStatus.QUEUED
    assert waiting.attempt_count == running.attempt_count == 1
    assert waiting.next_attempt_at == LATER
    assert waiting.phase == "waiting_to_retry"
    claimed = waiting.claim(LATER)
    assert claimed.attempt_count == 2 and claimed.next_attempt_at is None


def test_only_a_running_job_is_requeued_and_only_into_the_future() -> None:
    with pytest.raises(AiJobConflictError):
        _job("job-1", "req-1").requeue(NOW, LATER)
    with pytest.raises(InvalidAiJobError):
        _job("job-1", "req-1").claim(NOW).requeue(NOW, NOW)


def test_cancelling_a_waiting_job_clears_its_retry() -> None:
    waiting = _job("job-1", "req-1").claim(NOW).requeue(NOW, LATER)

    cancelled = waiting.request_cancellation(NOW)

    assert cancelled.status is AiJobStatus.CANCELLED and cancelled.next_attempt_at is None


@pytest.mark.parametrize(
    ("attempts", "seconds"), [(1, 30), (2, 60), (3, 120), (4, 240), (5, 300), (9, 300)]
)
def test_the_backoff_doubles_up_to_the_longest_wait(attempts: int, seconds: int) -> None:
    backoff = RetryBackoff(timedelta(seconds=30), timedelta(seconds=300))

    assert backoff.delay(attempts) == timedelta(seconds=seconds)


def test_a_backoff_needs_a_positive_first_wait_no_longer_than_the_longest() -> None:
    with pytest.raises(ValueError):
        RetryBackoff(timedelta(0), timedelta(seconds=300))
    with pytest.raises(ValueError):
        RetryBackoff(timedelta(seconds=60), timedelta(seconds=30))


def test_only_outages_that_pass_on_their_own_are_retried() -> None:
    assert TRANSIENT_FAILURE_CODES == {
        "model_rate_limit",
        "model_unavailable",
        "platform_service_unavailable",
    }


def test_a_waiting_job_holds_its_requirement_and_no_other() -> None:
    store = InMemoryAiJobStore(RLock())
    store.add(AiJobRecord(_job("first", "req-1"), AiJobCommand({"force": False})))
    store.add(
        AiJobRecord(
            _job("second", "req-1", NOW + timedelta(seconds=1)), AiJobCommand({"force": False})
        )
    )
    store.add(
        AiJobRecord(
            _job("elsewhere", "req-2", NOW + timedelta(seconds=2)), AiJobCommand({"force": False})
        )
    )
    first = store.claim_next("worker", NOW, NOW + timedelta(minutes=5))
    assert first is not None and first.job.id.value == "first"
    assert first.worker_id is not None and first.attempt_token is not None
    waiting = first.job.requeue(NOW, LATER)
    assert store.save_fenced(waiting, first.worker_id, first.attempt_token, NOW)

    before = store.claim_next("worker", NOW + timedelta(seconds=1), LATER)
    assert before is not None and before.job.id.value == "elsewhere"
    assert store.claim_next("worker", NOW + timedelta(seconds=1), LATER) is None

    again = store.claim_next("worker", LATER, LATER + timedelta(minutes=5))
    assert again is not None and again.job.id.value == "first"
    assert again.job.attempt_count == 2


def test_the_job_metric_tells_retries_and_exhaustion_from_failures() -> None:
    running = _job("job-1", "req-1").claim(NOW)
    failure = AiJobFailure("model_unavailable", "Provider unavailable.", True, "correlation")
    exhausted = AiJobFailure("attempts_exhausted", "Started too often.", True, "correlation")

    assert metric_status(running.requeue(NOW, LATER)) == "retrying"
    assert metric_status(running.fail(exhausted, NOW)) == "attempts_exhausted"
    assert metric_status(running.fail(failure, NOW)) == "failed"
    assert metric_status(running.succeed((), NOW)) == "succeeded"
