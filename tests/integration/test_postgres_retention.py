"""Finished jobs' inputs are cleared, and blob usage is reported, in PostgreSQL (ADR-0079).

Each test runs in its own schema: pruning and the blob report read whole tables.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import psycopg
import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.interfaces.api.composition.operations import build_retention
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobCommand, AiJobRecord
from smb_requirement_agent.jobs.domain.entities import (
    AiJob,
    AiJobId,
    AiJobOperation,
    AiJobStatus,
)
from smb_requirement_agent.jobs.infrastructure.postgres_ai_jobs import PostgresAiJobStore
from smb_requirement_agent.shared_kernel.actors import ActorId, ActorSnapshot
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.catalogue_scenarios import OWNER
from tests.integration.postgres_fixture_store import FixturePostgresStore

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
NOW = datetime.now(UTC)
LONG_AGO = NOW - timedelta(days=200)


class _NoWorklistProjection:
    def refresh(self, requirement_id: RequirementId) -> None:
        return None


@pytest.fixture
def schema_url() -> Iterator[str]:
    assert DATABASE_URL is not None
    schema = f"retention_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    url = f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    run_migrations(url)
    try:
        yield url
    finally:
        with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
            connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


@pytest.fixture
def client(schema_url: str) -> Iterator[TestClient]:
    container = build_container(
        Settings(
            llm_provider=LLMProvider.FAKE,
            persistence_provider=PersistenceProvider.POSTGRES,
            database_url=schema_url,
        )
    )
    try:
        with TestClient(create_app(lambda: container)) as test_client:
            yield test_client
    finally:
        container.close_resources()


def _requirement(client: TestClient) -> str:
    response = client.post(
        "/requirements",
        json={"title": "Fibre rollout", "description": "Fibre for SMB sites"},
        headers=OWNER,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _finished_job(
    jobs: PostgresAiJobStore,
    url: str,
    requirement_id: str,
    operation: AiJobOperation,
    status: AiJobStatus,
    completed_at: datetime | None,
) -> str:
    job_id = f"retention-{uuid.uuid4()}"
    job = AiJob(
        AiJobId(job_id),
        RequirementId(requirement_id),
        operation,
        AiJobStatus.QUEUED,
        ActorSnapshot(ActorId(OWNER["X-Fake-Actor-Id"]), "Owner"),
        LONG_AGO,
        LONG_AGO,
        f"retention-{uuid.uuid4()}",
        f"retention-{uuid.uuid4()}",
    )
    jobs.add(AiJobRecord(job, AiJobCommand({"answers": [{"question_id": "q", "answer": "a"}]})))
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(
            "UPDATE ai_jobs SET status=%s, completed_at=%s WHERE job_id=%s",
            (status.value, completed_at, job_id),
        )
    return job_id


def _commands(url: str) -> dict[str, tuple[object, bool]]:
    with psycopg.connect(url) as connection:
        rows = connection.execute(
            "SELECT job_id, command, payload_pruned_at IS NOT NULL FROM ai_jobs"
        ).fetchall()
    return {str(row[0]): (row[1], bool(row[2])) for row in rows}


def test_only_old_succeeded_and_cancelled_jobs_lose_their_inputs(
    client: TestClient, schema_url: str
) -> None:
    requirement = _requirement(client)
    jobs = PostgresAiJobStore(FixturePostgresStore(schema_url, _NoWorklistProjection()))

    def seed(operation: AiJobOperation, status: AiJobStatus, at: datetime | None) -> str:
        return _finished_job(jobs, schema_url, requirement, operation, status, at)

    resolve = AiJobOperation.RESOLVE_CLARIFICATION_QUESTIONS
    succeeded = seed(resolve, AiJobStatus.SUCCEEDED, LONG_AGO)
    cancelled = seed(AiJobOperation.ANALYSE_REQUIREMENT, AiJobStatus.CANCELLED, LONG_AGO)
    screen = seed(AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE, AiJobStatus.SUCCEEDED, LONG_AGO)
    failed = seed(AiJobOperation.ANALYSE_REQUIREMENT, AiJobStatus.FAILED, LONG_AGO)
    recent = seed(resolve, AiJobStatus.SUCCEEDED, NOW - timedelta(days=1))
    running = seed(AiJobOperation.ANALYSE_REQUIREMENT, AiJobStatus.RUNNING, None)

    # A batch of one still reaches every due job.
    assert jobs.prune_finished_inputs(NOW - timedelta(days=90), 1) == 2

    commands = _commands(schema_url)
    assert commands[succeeded] == ({}, True)
    assert commands[cancelled] == ({}, True)
    for kept in (screen, failed, recent, running):
        assert commands[kept][1] is False
        assert commands[kept][0] != {}
    # Rows stay, so the activity record is unchanged; a rerun finds nothing left to do.
    assert {succeeded, cancelled, screen, failed, recent, running} <= commands.keys()
    assert build_retention(schema_url).job_payloads.execute(timedelta(days=90)) == 0

    shown = client.get(f"/requirements/{requirement}/ai-jobs/{succeeded}", headers=OWNER)
    assert shown.status_code == 200, shown.text
    assert shown.json()["status"] == "succeeded"
    assert shown.json()["item_count"] is None

    retried = client.post(
        f"/requirements/{requirement}/ai-jobs/{cancelled}/retry",
        json={"expected_version": 1},
        headers={**OWNER, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert retried.status_code == 409, retried.text
    assert retried.json()["code"] == "ai_job_inputs_pruned"


def test_the_blob_report_counts_unreferenced_blobs_and_deletes_none(
    client: TestClient, schema_url: str
) -> None:
    requirement = _requirement(client)
    draft = client.post("/requirements/drafts", json={"title": "Draft"}, headers=OWNER).json()
    for path in (f"/requirements/{requirement}", f"/requirement-drafts/{draft['id']}"):
        attached = client.post(
            f"{path}/attachments",
            data={"include_in_analysis": "false"},
            files={"file": ("notes.txt", b"Policy text", "text/plain")},
            headers=OWNER,
        )
        assert attached.status_code == 201, attached.text
    report = build_retention(schema_url).blobs

    before = report.usage()
    assert before.count == 2
    assert before.size_bytes == 2 * len(b"Policy text")
    assert (before.orphan_count, before.orphan_size_bytes) == (0, 0)

    with psycopg.connect(schema_url, autocommit=True) as connection:
        connection.execute(
            "INSERT INTO document_blobs "
            "(document_version_id, checksum_sha256, size_bytes, content) VALUES (%s, %s, 5, %s)",
            ("orphan", "0" * 64, b"lost!"),
        )

    after = report.usage()
    assert (after.count, after.orphan_count, after.orphan_size_bytes) == (3, 1, 5)
    assert report.usage() == after
