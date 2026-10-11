"""The PostgreSQL outbox of closed and removed Epics: one per tracker event, leased
(ontology plan Phase 7)."""

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
from smb_requirement_agent.references.application.ports.delivery_closure import (
    DeliveryClosure,
    EpicOutcome,
)
from smb_requirement_agent.references.application.ports.knowledge_handoff import HandoffStatus
from smb_requirement_agent.references.infrastructure.delivery_closures import (
    PostgresDeliveryClosures,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
NOW = datetime(2026, 10, 20, 15, 30, tzinfo=UTC)
LEASE = timedelta(minutes=5)
BODY = {"delivery_id": "REQ-1:4711:evt-1", "state": "closed", "changes": []}


@pytest.fixture
def store() -> Iterator[PostgresStore]:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute("TRUNCATE delivery_closures")
    yield PostgresStore(
        DirectPostgresConnector(DATABASE_URL), lambda _id, _conn: None, lambda _c, _i: None
    )


def _closure(event: str, at: datetime = NOW) -> DeliveryClosure:
    return DeliveryClosure(
        closure_id=f"REQ-1:4711:{event}",
        requirement_id="REQ-1",
        epic_external_id="4711",
        outcome=EpicOutcome.CLOSED if event != "evt-removed" else EpicOutcome.REMOVED,
        occurred_at=at,
        created_at=at,
        next_attempt_at=at,
    )


def test_one_closure_per_event_and_it_reloads_as_queued(store: PostgresStore) -> None:
    outbox = PostgresDeliveryClosures(store)

    assert outbox.enqueue(_closure("evt-1")) is True
    assert outbox.enqueue(_closure("evt-1")) is False
    assert outbox.enqueue(_closure("evt-removed")) is True

    assert outbox.get("REQ-1:4711:evt-1") == _closure("evt-1")
    removed = outbox.get("REQ-1:4711:evt-removed")
    assert removed is not None and removed.outcome is EpicOutcome.REMOVED
    assert outbox.get("REQ-1:4711:evt-2") is None


def test_due_closures_are_leased_oldest_first_and_keep_their_body(store: PostgresStore) -> None:
    outbox = PostgresDeliveryClosures(store)
    outbox.enqueue(_closure("evt-2", NOW + timedelta(minutes=1)))
    outbox.enqueue(_closure("evt-1"))

    first = outbox.claim(NOW, LEASE, "w1")
    assert first is not None
    assert (first.closure_id, first.lease_token, first.attempts) == ("REQ-1:4711:evt-1", "w1", 1)
    assert outbox.claim(NOW, LEASE, "w2") is None
    rendered = first.rendered(BODY)
    outbox.save(rendered, first.version)

    # A lease that ran out is taken over, and the first worker's write is then refused.
    taken = outbox.claim(NOW + LEASE, LEASE, "w3")
    assert taken is not None and taken.closure_id == "REQ-1:4711:evt-1"
    assert taken.payload == BODY
    with pytest.raises(PersistenceError):
        outbox.save(rendered.delivered("CR-1", NOW), rendered.version)

    outbox.save(taken.delivered("CR-1", NOW + LEASE), taken.version)
    delivered = outbox.get("REQ-1:4711:evt-1")
    assert delivered is not None
    assert (delivered.status, delivered.change_request_id, delivered.payload) == (
        HandoffStatus.DELIVERED,
        "CR-1",
        BODY,
    )
    with psycopg.connect(DATABASE_URL or "") as connection:
        row = connection.execute(
            "SELECT status FROM delivery_closures WHERE closure_id='REQ-1:4711:evt-1'"
        ).fetchone()
    assert row == ("delivered",)
