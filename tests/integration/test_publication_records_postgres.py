"""The PostgreSQL publication record: whole-record payload, advanced one version at a time."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from smb_kernel.persistence.connector import DirectPostgresConnector

from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.governance.domain.publication.entities import (
    BacklogPublication,
    ExternalWorkItemMapping,
    ItemOutcome,
    ItemResult,
)
from smb_requirement_agent.governance.infrastructure.publication_records import (
    PostgresPublicationRecords,
)
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.infrastructure.persistence.postgres_store import PostgresStore
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
NOW = datetime(2026, 10, 10, 9, tzinfo=UTC)
REQUIREMENT = RequirementId("REQ-1")


@pytest.fixture
def store() -> Iterator[PostgresStore]:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute("TRUNCATE backlog_publications")
    yield PostgresStore(
        DirectPostgresConnector(DATABASE_URL), lambda _id, _conn: None, lambda _c, _i: None
    )


def _published() -> BacklogPublication:
    started = BacklogPublication(REQUIREMENT, "fake:local").start(
        2, "owner-1", "Owner", NOW, NOW + timedelta(minutes=15)
    )
    mapping = ExternalWorkItemMapping(
        "epic-1", "epic", "101", "https://tracker/101", "sha256:1", 2, NOW
    )
    return started.record(ItemOutcome("epic-1", ItemResult.CREATED), mapping).finish(NOW)


def test_a_record_reloads_whole(store: PostgresStore) -> None:
    records = PostgresPublicationRecords(store)
    publication = _published()

    records.save(publication)

    assert records.get(REQUIREMENT) == publication
    assert records.get(RequirementId("REQ-2")) is None


def test_each_save_advances_the_stored_record_by_one_version(store: PostgresStore) -> None:
    records = PostgresPublicationRecords(store)
    started = BacklogPublication(REQUIREMENT, "fake:local").start(
        2, "owner-1", "Owner", NOW, NOW + timedelta(minutes=15)
    )
    records.save(started)

    finished = started.finish(NOW)
    records.save(finished)

    assert records.get(REQUIREMENT) == finished
    with pytest.raises(ArtifactVersionConflictError):
        records.save(started.finish(NOW + timedelta(seconds=1)))
    with pytest.raises(ArtifactVersionConflictError):
        records.save(started)
    assert records.get(REQUIREMENT) == finished


def test_a_record_saved_in_a_failed_transaction_is_not_kept(store: PostgresStore) -> None:
    records = PostgresPublicationRecords(store)

    with pytest.raises(RuntimeError), store.transaction():
        records.save(_published())
        raise RuntimeError("The attempt failed.")

    assert records.get(REQUIREMENT) is None
