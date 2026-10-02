"""The requirement mapping job queue reports storage failures as `PersistenceError`.

A driver error must never escape as a raw `psycopg` exception, and a stored row
the code cannot interpret must fail loudly rather than become a wrong job. The
state transitions themselves run against PostgreSQL in
`tests/integration/test_postgres_architecture_jobs.py`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import psycopg
import pytest

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobKind,
    ArchitectureJobStatus,
    MappingJobInput,
)
from smb_requirement_agent.infrastructure.persistence.postgres_architecture_jobs import (
    PostgresArchitectureJobs,
)
from smb_requirement_agent.infrastructure.persistence.postgres_values import DbConnection

NOW = datetime(2026, 9, 25, 12, tzinfo=UTC)
KEY = MappingJobInput("release-1", "fingerprint", "embedding", "reasoning").key
JOB = ArchitectureJob(
    "job-1", ArchitectureJobKind.MAPPING, "req-1", KEY, "editor", ArchitectureJobStatus.QUEUED
)


class _UnavailableConnector:
    """A `PostgresConnector` whose database is down."""

    def acquire(self) -> DbConnection:
        raise psycopg.OperationalError("database unavailable")

    def release(self, connection: DbConnection) -> None:
        connection.close()

    @contextmanager
    def connection(self, timeout_seconds: float | None = None) -> Iterator[DbConnection]:
        yield self.acquire()

    def close(self) -> None:
        return None


@pytest.mark.parametrize(
    ("call", "message"),
    [
        pytest.param(lambda jobs: jobs.enqueue(JOB), "could not be queued", id="enqueue"),
        pytest.param(lambda jobs: jobs.get("job-1"), "read failed", id="get"),
        pytest.param(lambda jobs: jobs.claim(NOW), "claim failed", id="claim"),
        pytest.param(lambda jobs: jobs.heartbeat("job-1", 1, NOW), "heartbeat failed", id="beat"),
        pytest.param(
            lambda jobs: jobs.finish("job-1", 1, ArchitectureJobStatus.SUCCEEDED, None),
            "completion failed",
            id="finish",
        ),
        pytest.param(lambda jobs: jobs.cancel("job-1"), "state update failed", id="cancel"),
        pytest.param(lambda jobs: jobs.retry("job-1"), "state update failed", id="retry"),
    ],
)
def test_a_driver_error_becomes_a_persistence_error(
    call: Callable[[PostgresArchitectureJobs], object], message: str
) -> None:
    jobs = PostgresArchitectureJobs(_UnavailableConnector())

    with pytest.raises(PersistenceError, match=message) as raised:
        call(jobs)

    assert isinstance(raised.value.__cause__, psycopg.OperationalError)


def _row(**changes: object) -> tuple[object, ...]:
    row: dict[str, object] = {
        "id": "job-1",
        "kind": "mapping",
        "subject": "req-1",
        "fingerprint": KEY,
        "actor": "editor",
        "status": "queued",
        "attempts": 0,
        "error": None,
        "lease": None,
    }
    row.update(changes)
    return tuple(row.values())


@pytest.mark.parametrize(
    ("row", "message"),
    [
        pytest.param(_row(attempts="1"), "attempt count", id="attempts"),
        pytest.param(_row(kind="reindex"), "kind or status", id="kind"),
        # The catalogue's own jobs left with the catalogue (ADR-0099).
        pytest.param(_row(kind="index"), "kind or status", id="catalogue kind"),
        pytest.param(_row(status="paused"), "kind or status", id="status"),
    ],
)
def test_an_uninterpretable_stored_row_fails_loudly(row: tuple[object, ...], message: str) -> None:
    with pytest.raises(PersistenceError, match=message):
        PostgresArchitectureJobs._job(row)


def test_a_stored_row_maps_to_a_job() -> None:
    job = PostgresArchitectureJobs._job(_row(status="running", attempts=2, lease=NOW))

    assert job.kind is ArchitectureJobKind.MAPPING
    assert MappingJobInput.from_key(job.fingerprint).release_id == "release-1"
    assert job.status is ArchitectureJobStatus.RUNNING
    assert job.attempts == 2
    assert job.lease_until == NOW
