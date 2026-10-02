"""Mapping jobs move to the requirement mapping queue, intact (ADR-0099).

The migration test runs the real migrations in a throwaway schema: up to the
previous head, then catalogue and mapping jobs in the shared queue, then the
moving migration. The shared test schema is never touched.
"""

from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import psycopg
import pytest
from smb_kernel.persistence.connector import DirectPostgresConnector

from smb_requirement_agent.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobKind,
    ArchitectureJobStatus,
)
from smb_requirement_agent.infrastructure.persistence import migration_runner
from smb_requirement_agent.infrastructure.persistence.postgres_architecture_jobs import (
    PostgresArchitectureJobs,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
MOVING = "202610021100_requirement_mapping_jobs.sql"


@pytest.fixture
def isolated_url() -> Iterator[str]:
    assert DATABASE_URL is not None
    schema = f"mapping_jobs_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    # public stays on the path for the vector extension's types.
    yield f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def test_mapping_jobs_leave_the_catalogue_queue_with_their_state(
    isolated_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = Path(migration_runner.MIGRATIONS)
    for path in real.glob("*.sql"):
        if path.name != MOVING:
            shutil.copy(path, tmp_path / path.name)
    monkeypatch.setattr(migration_runner, "MIGRATIONS", tmp_path)
    migration_runner.run_migrations(isolated_url)
    lease = datetime(2026, 10, 2, 9, 5, tzinfo=UTC)
    with psycopg.connect(isolated_url) as connection:
        connection.execute(
            "INSERT INTO architecture_jobs (job_id, kind, subject_id, fingerprint, actor_id, "
            "status, attempts, lease_until, error_category) VALUES "
            "('index-1', 'index', 'release-1', '3|profile', 'maintainer', 'queued', 0, NULL, NULL),"
            "('map-1', 'mapping', 'req-1', 'release-1|abc|e|r', 'owner', 'running', 2, %s, NULL),"
            "('map-2', 'mapping', 'req-2', 'release-1|def|e|r', 'owner', 'failed', 3, NULL, "
            "'attempts_exhausted')",
            (lease,),
        )

    shutil.copy(real / MOVING, tmp_path / MOVING)
    migration_runner.run_migrations(isolated_url)

    with psycopg.connect(isolated_url) as connection:
        catalogue = connection.execute("SELECT job_id FROM architecture_jobs").fetchall()
        mapping = connection.execute(
            "SELECT job_id, subject_id, fingerprint, actor_id, status, attempts, lease_until, "
            "error_category FROM requirement_mapping_jobs ORDER BY job_id"
        ).fetchall()
    assert catalogue == [("index-1",)]
    assert mapping == [
        ("map-1", "req-1", "release-1|abc|e|r", "owner", "running", 2, lease, None),
        ("map-2", "req-2", "release-1|def|e|r", "owner", "failed", 3, None, "attempts_exhausted"),
    ]


def test_the_mapping_queue_leases_independently_of_the_catalogue_queue() -> None:
    assert DATABASE_URL is not None
    migration_runner.run_migrations(DATABASE_URL)
    connector = DirectPostgresConnector(DATABASE_URL)
    catalogue = PostgresArchitectureJobs(connector)
    mapping = PostgresArchitectureJobs(connector, table="requirement_mapping_jobs")
    subject = f"req-{uuid.uuid4().hex}"
    queued = mapping.enqueue(
        ArchitectureJob(
            uuid.uuid4().hex,
            ArchitectureJobKind.MAPPING,
            subject,
            "release|fingerprint|e|r",
            "owner",
            ArchitectureJobStatus.QUEUED,
        )
    )

    assert catalogue.get(queued.id) is None
    assert mapping.for_subject(ArchitectureJobKind.MAPPING, subject) == (queued,)
    claimed = mapping.claim(datetime.now(UTC))
    while claimed is not None and claimed.id != queued.id:
        mapping.finish(claimed.id, claimed.attempts, ArchitectureJobStatus.SUCCEEDED, None)
        claimed = mapping.claim(datetime.now(UTC))
    assert claimed is not None and claimed.status is ArchitectureJobStatus.RUNNING
    mapping.finish(claimed.id, claimed.attempts, ArchitectureJobStatus.SUCCEEDED, None)
    finished = mapping.get(queued.id)
    assert finished is not None and finished.status is ArchitectureJobStatus.SUCCEEDED


def test_only_known_job_tables_reach_sql() -> None:
    with pytest.raises(ValueError, match="Unknown job table"):
        PostgresArchitectureJobs(DirectPostgresConnector("postgresql://unused"), table="x; DROP")
