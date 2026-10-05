"""The PostgreSQL outbox of approved backlogs: one per approval, transactional, leased."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from smb_kernel.persistence.connector import DirectPostgresConnector

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.application.ports.knowledge_handoff import (
    BacklogHandoff,
    HandoffStatus,
)
from smb_requirement_agent.infrastructure.persistence.backlog_handoffs import (
    PostgresBacklogHandoffs,
)
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.infrastructure.persistence.postgres_store import PostgresStore

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
NOW = datetime(2026, 10, 5, 9, tzinfo=UTC)
LEASE = timedelta(minutes=5)


@pytest.fixture
def store() -> Iterator[PostgresStore]:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute("TRUNCATE approved_backlog_handoffs")
    yield PostgresStore(
        DirectPostgresConnector(DATABASE_URL), lambda _id, _conn: None, lambda _c, _i: None
    )


def _handoff(approval_id: str, at: datetime = NOW) -> BacklogHandoff:
    return BacklogHandoff(
        approval_id=approval_id,
        requirement_id="REQ-1",
        subject_fingerprint="sha256:1",
        created_at=at,
        next_attempt_at=at,
    )


def test_one_handoff_per_approval_and_it_reloads_as_queued(store: PostgresStore) -> None:
    outbox = PostgresBacklogHandoffs(store)

    assert outbox.enqueue(_handoff("apr-1")) is True
    assert outbox.enqueue(_handoff("apr-1")) is False

    assert outbox.get("apr-1") == _handoff("apr-1")
    assert outbox.get("apr-2") is None


def test_a_handoff_is_queued_with_its_transaction_or_not_at_all(store: PostgresStore) -> None:
    outbox = PostgresBacklogHandoffs(store)

    with pytest.raises(RuntimeError), store.transaction():
        outbox.enqueue(_handoff("apr-1"))
        raise RuntimeError("The approval failed.")

    assert outbox.get("apr-1") is None
    with store.transaction():
        outbox.enqueue(_handoff("apr-1"))
    assert outbox.get("apr-1") is not None


def test_due_handoffs_are_leased_oldest_first_to_one_worker(store: PostgresStore) -> None:
    outbox = PostgresBacklogHandoffs(store)
    outbox.enqueue(_handoff("apr-later", NOW + timedelta(minutes=1)))
    outbox.enqueue(_handoff("apr-first"))

    first = outbox.claim(NOW, LEASE, "w1")
    assert first is not None
    assert (first.approval_id, first.lease_token, first.attempts) == ("apr-first", "w1", 1)
    # The later one is not due yet, and the leased one is held.
    assert outbox.claim(NOW, LEASE, "w2") is None
    later = outbox.claim(NOW + timedelta(minutes=1), LEASE, "w2")
    assert later is not None and later.approval_id == "apr-later"

    # A lease that ran out is taken over, and the first worker's write is then refused.
    taken = outbox.claim(NOW + LEASE, LEASE, "w3")
    assert taken is not None and taken.approval_id == "apr-first"
    with pytest.raises(PersistenceError):
        outbox.save(first.delivered("CR-1", NOW), first.version)

    outbox.save(taken.delivered("CR-1", NOW + LEASE), taken.version)
    delivered = outbox.get("apr-first")
    assert delivered is not None
    assert (delivered.status, delivered.change_request_id) == (HandoffStatus.DELIVERED, "CR-1")
    with psycopg.connect(DATABASE_URL or "") as connection:
        row = connection.execute(
            "SELECT status FROM approved_backlog_handoffs WHERE approval_id='apr-first'"
        ).fetchone()
    assert row == ("delivered",)
