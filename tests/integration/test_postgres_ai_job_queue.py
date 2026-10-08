"""The production AI job queue fences every attempt write, in PostgreSQL.

A worker that lost its lease must not report progress, heartbeat or finish a
job another worker now owns. Idempotency keys bind one command to one job.
Notification preferences default to off. The in-memory queue has the same
tests in `tests/unit/jobs/test_ai_jobs.py`; these prove the SQL does the same.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobCommand, AiJobRecord
from smb_requirement_agent.jobs.domain.entities import (
    ActorNotification,
    AiJob,
    AiJobId,
    AiJobOperation,
    AiJobStatus,
    NotificationId,
    NotificationKind,
    NotificationPreference,
)
from smb_requirement_agent.jobs.domain.errors import AiJobConflictError
from smb_requirement_agent.jobs.infrastructure.postgres_ai_jobs import (
    PostgresAiJobStore,
    PostgresNotificationRepository,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorSnapshot,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.integration.postgres_fixture_store import FixturePostgresStore

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
# The shared database's queue may hold other tests' jobs: this one is the
# oldest, and only its operation is claimable, so the claims below are ours.
CREATED = datetime(2000, 1, 1, tzinfo=UTC)
OPERATION = AiJobOperation.SUGGEST_CLARIFICATION_ANSWERS
BLOCKED = tuple(item for item in AiJobOperation if item is not OPERATION)


class _NoWorklistProjection:
    def refresh(self, requirement_id: RequirementId) -> None:
        return None


def _store() -> FixturePostgresStore:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    return FixturePostgresStore(DATABASE_URL, _NoWorklistProjection())


@pytest.fixture(autouse=True)
def _only_this_tests_jobs() -> Iterator[None]:
    """Remove this module's jobs, so no earlier test or run leaves one to be claimed."""

    def clear() -> None:
        with _store().connection() as connection:
            connection.execute(
                "UPDATE requirement_ai_job_leases SET job_id=NULL, worker_id=NULL, "
                "attempt_token=NULL, leased_until=NULL WHERE job_id LIKE 'fence-%'"
            )
            connection.execute("DELETE FROM ai_jobs WHERE job_id LIKE 'fence-%'")

    clear()
    yield
    clear()


def _queued_job(
    store: FixturePostgresStore, operation: AiJobOperation = OPERATION
) -> tuple[PostgresAiJobStore, AiJob]:
    requirement_id = RequirementId(str(uuid.uuid4()))
    store.add(
        Requirement(
            requirement_id,
            RequirementTitle("Queue fencing"),
            RequirementDescription("Only the current attempt may write."),
            RequirementStatus.DRAFT,
        )
    )
    jobs = PostgresAiJobStore(store)
    job = AiJob(
        AiJobId(f"fence-{uuid.uuid4()}"),
        requirement_id,
        operation,
        AiJobStatus.QUEUED,
        ActorSnapshot(ActorId("fake-owner"), "Owner"),
        CREATED,
        CREATED,
        f"fence-{uuid.uuid4()}",
        f"fence-{uuid.uuid4()}",
    )
    jobs.add(AiJobRecord(job, AiJobCommand({"question_id": "q-1", "expected_version": 1})))
    return jobs, job


def test_an_idempotency_key_binds_one_command_to_one_job() -> None:
    jobs, job = _queued_job(_store())
    actor = ActorId(f"idem-{uuid.uuid4()}")

    jobs.bind_idempotency(job.id, actor, "key-1", job.command_fingerprint)
    jobs.bind_idempotency(job.id, actor, "key-1", job.command_fingerprint)  # repeat is fine

    found = jobs.get_by_idempotency(actor, "key-1")
    assert found is not None and found.job.id == job.id
    assert jobs.get_by_idempotency(actor, "key-unknown") is None
    with pytest.raises(AiJobConflictError, match="Idempotency-Key"):
        jobs.bind_idempotency(job.id, actor, "key-1", "another-command")


def test_only_the_current_attempt_can_write_and_a_fenced_one_cannot() -> None:
    jobs, job = _queued_job(_store())
    now = datetime.now(UTC)
    lease = now + timedelta(minutes=5)

    first = jobs.claim_next("worker-a", now, lease, BLOCKED)
    assert first is not None and first.job.id == job.id and first.attempt_token is not None
    assert first.job.status is AiJobStatus.RUNNING

    progressed = first.job.report_progress("screening", 1, 3, "Section 1", now)
    assert jobs.report_progress_fenced(progressed, "worker-a", first.attempt_token, now)
    assert not jobs.report_progress_fenced(
        progressed.report_progress("screening", 2, 3, None, now), "worker-a", "stale", now
    )
    assert jobs.heartbeat(job.id, "worker-a", first.attempt_token, now, lease)
    assert not jobs.heartbeat(job.id, "worker-a", "stale", now, lease)

    # The lease is taken away: the first attempt can no longer write anything.
    assert jobs.fence_attempt(job.id, "worker-a", first.attempt_token)
    assert not jobs.fence_attempt(job.id, "worker-a", first.attempt_token)
    stored = jobs.get(job.id)
    assert stored is not None
    assert not jobs.save_fenced(stored.job.succeed((), now), "worker-a", first.attempt_token, now)

    # Another worker reclaims it, finishes it, and releases the Requirement.
    later = now + timedelta(seconds=5)
    second = jobs.claim_next("worker-b", later, later + timedelta(minutes=5), BLOCKED)
    assert second is not None and second.job.id == job.id and second.attempt_token is not None
    assert second.job.attempt_count == first.job.attempt_count + 1
    assert jobs.save_fenced(second.job.succeed((), later), "worker-b", second.attempt_token, later)
    jobs.release(job.id, "worker-b", second.attempt_token)

    finished = jobs.get(job.id)
    assert finished is not None and finished.job.status is AiJobStatus.SUCCEEDED
    assert finished.worker_id is None and finished.attempt_token is None


@pytest.mark.parametrize(
    ("operation", "phase"),
    [
        (AiJobOperation.SUGGEST_CLARIFICATION_ANSWERS, "running"),
        (AiJobOperation.ANALYSE_REQUIREMENT, "preparing_analysis"),
    ],
)
def test_a_claim_and_a_reclaim_start_the_attempt_with_no_progress(
    operation: AiJobOperation, phase: str
) -> None:
    jobs, job = _queued_job(_store(), operation)
    blocked = tuple(item for item in AiJobOperation if item is not operation)
    now = datetime.now(UTC)

    first = jobs.claim_next("worker-a", now, now + timedelta(seconds=1), blocked)
    assert first is not None and first.job.id == job.id and first.attempt_token is not None
    assert (first.job.phase, first.job.completed_units, first.job.total_units) == (phase, 0, None)
    progressed = first.job.report_progress("screening", 2, 3, "Section 2", now)
    assert jobs.report_progress_fenced(progressed, "worker-a", first.attempt_token, now)

    # The first worker dies; once its lease runs out another worker reclaims the job.
    later = now + timedelta(seconds=5)
    second = jobs.claim_next("worker-b", later, later + timedelta(minutes=5), blocked)
    assert second is not None and second.job.id == job.id
    assert second.job.attempt_count == first.job.attempt_count + 1
    assert second.job.phase == phase
    assert second.job.completed_units == 0
    assert second.job.total_units is None
    assert second.job.current_section_label is None
    assert second.job.failure is None


def test_notifications_round_trip_and_preferences_default_to_off() -> None:
    store = _store()
    jobs, job = _queued_job(store)
    notifications = PostgresNotificationRepository(store)
    actor = ActorId(f"notify-{uuid.uuid4()}")
    note = ActorNotification(
        NotificationId(f"note-{uuid.uuid4()}"),
        actor,
        job.id,
        NotificationKind.AI_JOB_FAILED,
        "Failed.",
        datetime.now(UTC),
        "/requirements/x/clarify",
    )

    notifications.add(note)
    assert notifications.get(note.id) == note
    read = note.mark_read(datetime.now(UTC))
    notifications.save(read)
    assert notifications.get(note.id) == read
    assert notifications.list_for_actor(actor, unread_only=True) == []
    assert notifications.get(NotificationId("missing")) is None

    assert notifications.get_preference(actor) == NotificationPreference(actor, False)
    notifications.save_preference(NotificationPreference(actor, True))
    notifications.save_preference(NotificationPreference(actor, True))  # upsert
    assert notifications.get_preference(actor).browser_enabled is True
    assert jobs.get(job.id) is not None
