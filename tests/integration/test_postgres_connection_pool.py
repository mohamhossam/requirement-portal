"""The pooled connector under the real unit of work.

A one-connection pool makes every leak observable: if a unit of work, an
external call, or an error path failed to return its connection, the next
acquisition would time out instead of succeeding.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator

import psycopg
import pytest
from psycopg.pq import TransactionStatus

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.infrastructure.persistence.postgres_connector import (
    PooledPostgresConnector,
)
from smb_requirement_agent.infrastructure.persistence.postgres_store import PostgresStore

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
MARKER = "connection-pool-integration-test"


@pytest.fixture
def connector() -> Iterator[PooledPostgresConnector]:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    pool = PooledPostgresConnector(
        DATABASE_URL,
        min_size=1,
        max_size=1,
        acquire_timeout_seconds=1,
        max_idle_seconds=60,
    )
    pool.open()
    try:
        yield pool
    finally:
        pool.close()
        with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
            connection.execute("DELETE FROM maintenance_markers WHERE name=%s", (MARKER,))


def _store(connector: PooledPostgresConnector) -> PostgresStore:
    return PostgresStore(connector, lambda *_: None, lambda *_: None)


def _backend_pid(store: PostgresStore) -> int:
    with store.connection() as connection:
        row = connection.execute("SELECT pg_backend_pid()").fetchone()
    assert row is not None and isinstance(row[0], int)
    return row[0]


def _marker_exists(store: PostgresStore) -> bool:
    with store.connection() as connection:
        row = connection.execute(
            "SELECT EXISTS (SELECT 1 FROM maintenance_markers WHERE name=%s)", (MARKER,)
        ).fetchone()
    return row is not None and bool(row[0])


def test_units_of_work_reuse_one_pooled_session(connector: PooledPostgresConnector) -> None:
    store = _store(connector)

    first = _backend_pid(store)
    second = _backend_pid(store)

    assert first == second


def test_committed_and_rejected_work_both_return_a_clean_connection(
    connector: PooledPostgresConnector,
) -> None:
    store = _store(connector)

    with store.transaction():
        with store.connection() as connection:
            connection.execute("INSERT INTO maintenance_markers (name) VALUES (%s)", (MARKER,))
        store.mark_rollback_only()
    assert _marker_exists(store) is False

    with pytest.raises(RuntimeError, match="business rule"):
        with store.transaction():
            with store.connection() as connection:
                connection.execute("INSERT INTO maintenance_markers (name) VALUES (%s)", (MARKER,))
            raise RuntimeError("business rule rejected the change")
    assert _marker_exists(store) is False

    with store.transaction():
        with store.connection() as connection:
            connection.execute("INSERT INTO maintenance_markers (name) VALUES (%s)", (MARKER,))
    assert _marker_exists(store) is True

    borrowed = connector.acquire()
    try:
        assert borrowed.info.transaction_status is TransactionStatus.IDLE
    finally:
        connector.release(borrowed)


def test_external_call_returns_the_connection_while_the_provider_runs(
    connector: PooledPostgresConnector,
) -> None:
    store = _store(connector)
    used_during_call: list[int] = []

    def provider_side_read() -> None:
        # Another thread (e.g. a progress read) needs the only pooled connection.
        with connector.connection() as connection:
            row = connection.execute("SELECT 1").fetchone()
            used_during_call.append(row[0] if row and isinstance(row[0], int) else 0)

    with store.transaction():
        _backend_pid(store)
        with store.external_call():
            reader = threading.Thread(target=provider_side_read)
            reader.start()
            reader.join(timeout=5)
        with store.connection() as connection:
            connection.execute("INSERT INTO maintenance_markers (name) VALUES (%s)", (MARKER,))

    assert used_during_call == [1]
    assert _marker_exists(store) is True


def test_exhausted_pool_fails_the_unit_of_work_instead_of_hanging(
    connector: PooledPostgresConnector,
) -> None:
    store = _store(connector)
    held = connector.acquire()
    try:
        with pytest.raises(PersistenceError):
            with store.transaction():
                pass
    finally:
        connector.release(held)

    assert _backend_pid(store) > 0


def test_readiness_uses_the_pool(connector: PooledPostgresConnector) -> None:
    assert DATABASE_URL is not None
    store = _store(connector)
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(
            "INSERT INTO maintenance_markers (name) VALUES ('activity-worklist-v2') "
            "ON CONFLICT DO NOTHING"
        )

    assert store.readiness() is True

    connector.close()
    assert store.readiness() is False
