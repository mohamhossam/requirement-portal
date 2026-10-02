"""Architecture job state transitions against PostgreSQL.

The happy path (enqueue, claim, heartbeat, finish) runs in
`test_postgres_architecture.py`. These cover what an operator relies on when
it goes wrong: a job that keeps failing stops being retried, a failed job can
be retried by hand, a queued job can be cancelled, a re-enqueued failure is
queued again, and a transition from the wrong state is a conflict.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from smb_kernel.persistence.connector import (
    DirectPostgresConnector,
)

from smb_requirement_agent.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobKind,
    ArchitectureJobStatus,
)
from smb_requirement_agent.domain.architecture.knowledge import KnowledgeConflictError
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.infrastructure.persistence.postgres_architecture_jobs import (
    PostgresArchitectureJobs,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")


@pytest.fixture
def jobs() -> Iterator[PostgresArchitectureJobs]:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    connector = DirectPostgresConnector(DATABASE_URL)
    # `claim` takes the oldest claimable job in the table, so start with none.
    # Finished jobs are left alone; only claimable ones would interfere.
    with connector.connection() as connection:
        connection.execute("DELETE FROM architecture_jobs WHERE status IN ('queued', 'running')")
    yield PostgresArchitectureJobs(connector)


def _enqueue(jobs: PostgresArchitectureJobs) -> ArchitectureJob:
    return jobs.enqueue(
        ArchitectureJob(
            uuid4().hex,
            ArchitectureJobKind.INDEX,
            f"draft-{uuid4().hex}",
            "1",
            "knowledge-editor",
            ArchitectureJobStatus.QUEUED,
        )
    )


def test_a_job_that_keeps_failing_stops_after_three_attempts(
    jobs: PostgresArchitectureJobs,
) -> None:
    job = _enqueue(jobs)
    now = datetime.now(UTC)
    for attempt in (1, 2, 3):
        claimed = jobs.claim(now)
        assert claimed is not None and claimed.id == job.id and claimed.attempts == attempt
        # The worker dies: the lease lapses without a finish.
        now = now + timedelta(minutes=6)

    assert jobs.claim(now) is None

    exhausted = jobs.get(job.id)
    assert exhausted is not None
    assert exhausted.status is ArchitectureJobStatus.FAILED
    assert exhausted.error_category == "attempts_exhausted"
    assert exhausted.lease_until is None


def test_a_failed_job_can_be_retried_and_starts_its_attempts_again(
    jobs: PostgresArchitectureJobs,
) -> None:
    job = _enqueue(jobs)
    claimed = jobs.claim(datetime.now(UTC))
    assert claimed is not None
    jobs.finish(job.id, claimed.attempts, ArchitectureJobStatus.FAILED, "provider")

    retried = jobs.retry(job.id)

    assert retried.status is ArchitectureJobStatus.QUEUED
    assert retried.attempts == 0 and retried.error_category is None
    with pytest.raises(KnowledgeConflictError, match="Only a failed job"):
        jobs.retry(job.id)


def test_a_queued_job_can_be_cancelled_but_not_twice(jobs: PostgresArchitectureJobs) -> None:
    job = _enqueue(jobs)

    cancelled = jobs.cancel(job.id)

    assert cancelled.status is ArchitectureJobStatus.CANCELLED
    assert jobs.claim(datetime.now(UTC)) is None
    with pytest.raises(KnowledgeConflictError, match="Only a queued job"):
        jobs.cancel(job.id)


def test_re_enqueueing_a_cancelled_job_queues_it_again(jobs: PostgresArchitectureJobs) -> None:
    job = _enqueue(jobs)
    jobs.cancel(job.id)

    again = jobs.enqueue(
        ArchitectureJob(
            uuid4().hex,
            job.kind,
            job.subject_id,
            job.fingerprint,
            job.actor_id,
            ArchitectureJobStatus.QUEUED,
        )
    )

    assert again.id == job.id
    assert again.status is ArchitectureJobStatus.QUEUED


def test_a_finished_attempt_cannot_heartbeat(jobs: PostgresArchitectureJobs) -> None:
    job = _enqueue(jobs)
    claimed = jobs.claim(datetime.now(UTC))
    assert claimed is not None
    jobs.finish(job.id, claimed.attempts, ArchitectureJobStatus.SUCCEEDED, None)

    assert not jobs.heartbeat(job.id, claimed.attempts, datetime.now(UTC))
    assert jobs.get(uuid4().hex) is None


def test_asking_again_for_an_exhausted_job_resets_its_attempts(
    jobs: PostgresArchitectureJobs,
) -> None:
    job = _enqueue(jobs)
    now = datetime.now(UTC)
    for _ in range(3):
        assert jobs.claim(now) is not None
        now = now + timedelta(minutes=6)
    assert jobs.claim(now) is None

    again = jobs.enqueue(
        ArchitectureJob(
            uuid4().hex,
            job.kind,
            job.subject_id,
            job.fingerprint,
            job.actor_id,
            ArchitectureJobStatus.QUEUED,
        )
    )

    assert (again.id, again.status, again.attempts) == (job.id, ArchitectureJobStatus.QUEUED, 0)
    assert again.error_category is None
    claimed = jobs.claim(now)
    assert claimed is not None and claimed.id == job.id
    assert jobs.for_subject(job.kind, job.subject_id) == (jobs.get(job.id),)
