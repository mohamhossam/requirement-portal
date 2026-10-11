"""The PostgreSQL outbox of decided verdicts: one per analysis version, transactional, leased."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from smb_kernel.persistence.connector import DirectPostgresConnector

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.infrastructure.persistence.postgres_store import PostgresStore
from smb_requirement_agent.references.application.ports.knowledge_handoff import HandoffStatus
from smb_requirement_agent.references.application.ports.precedent_handoff import (
    PrecedentHandoff,
)
from smb_requirement_agent.references.infrastructure.precedent_handoffs import (
    PostgresPrecedentHandoffs,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
NOW = datetime(2026, 10, 11, 9, tzinfo=UTC)
LEASE = timedelta(minutes=5)


@pytest.fixture
def store() -> Iterator[PostgresStore]:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute("TRUNCATE precedent_handoffs")
    yield PostgresStore(
        DirectPostgresConnector(DATABASE_URL), lambda _id, _conn: None, lambda _c, _i: None
    )


def _handoff(handoff_id: str, at: datetime = NOW) -> PrecedentHandoff:
    return PrecedentHandoff(
        handoff_id=handoff_id,
        requirement_id="REQ-1",
        payload={
            "precedent_id": "ANA-1",
            "text": ["Static IP quota"],
            "systems": [{"id": "bcrm", "role": "primary", "change_type": "modify"}],
        },
        created_at=at,
        next_attempt_at=at,
    )


def test_one_handoff_per_version_and_it_reloads_as_queued(store: PostgresStore) -> None:
    outbox = PostgresPrecedentHandoffs(store)

    assert outbox.enqueue(_handoff("ANA-1@3")) is True
    assert outbox.enqueue(_handoff("ANA-1@3")) is False

    assert outbox.get("ANA-1@3") == _handoff("ANA-1@3")
    assert outbox.get("ANA-1@4") is None


def test_a_handoff_is_queued_with_its_transaction_or_not_at_all(store: PostgresStore) -> None:
    outbox = PostgresPrecedentHandoffs(store)

    with pytest.raises(RuntimeError), store.transaction():
        outbox.enqueue(_handoff("ANA-1@3"))
        raise RuntimeError("The decision failed.")

    assert outbox.get("ANA-1@3") is None
    with store.transaction():
        outbox.enqueue(_handoff("ANA-1@3"))
    assert outbox.get("ANA-1@3") is not None


def test_due_handoffs_are_leased_oldest_first_to_one_worker(store: PostgresStore) -> None:
    outbox = PostgresPrecedentHandoffs(store)
    outbox.enqueue(_handoff("ANA-2@1", NOW + timedelta(minutes=1)))
    outbox.enqueue(_handoff("ANA-1@3"))

    first = outbox.claim(NOW, LEASE, "w1")
    assert first is not None
    assert (first.handoff_id, first.lease_token, first.attempts) == ("ANA-1@3", "w1", 1)
    # The later one is not due yet, and the leased one is held.
    assert outbox.claim(NOW, LEASE, "w2") is None
    later = outbox.claim(NOW + timedelta(minutes=1), LEASE, "w2")
    assert later is not None and later.handoff_id == "ANA-2@1"

    # A lease that ran out is taken over, and the first worker's write is then refused.
    taken = outbox.claim(NOW + LEASE, LEASE, "w3")
    assert taken is not None and taken.handoff_id == "ANA-1@3"
    with pytest.raises(PersistenceError):
        outbox.save(first.delivered(NOW), first.version)

    outbox.save(taken.delivered(NOW + LEASE), taken.version)
    delivered = outbox.get("ANA-1@3")
    assert delivered is not None
    assert (delivered.status, delivered.payload) == (
        HandoffStatus.DELIVERED,
        _handoff("ANA-1@3").payload,
    )
    with psycopg.connect(DATABASE_URL or "") as connection:
        row = connection.execute(
            "SELECT status FROM precedent_handoffs WHERE handoff_id='ANA-1@3'"
        ).fetchone()
    assert row == ("delivered",)
