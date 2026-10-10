"""Pooled sessions are bounded, and a busy database answers 503 (production hardening PR 3).

Every pooled connection carries `statement_timeout`, `lock_timeout` and
`idle_in_transaction_session_timeout`. A statement or lock wait past its limit
reaches callers as `DatabaseBusyError`, which the API answers with 503
`database_busy`. The pool reports its connections to the metrics exporter.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator
from dataclasses import replace
from urllib.parse import quote

import psycopg
import pytest
from fastapi.testclient import TestClient
from prometheus_client import generate_latest
from smb_kernel.persistence.connector import PooledPostgresConnector

from smb_requirement_agent.application.errors import DatabaseBusyError
from smb_requirement_agent.governance.infrastructure.postgres_revisions import (
    PostgresRevisionWriter,
)
from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.infrastructure.persistence.postgres_store import PostgresStore
from smb_requirement_agent.interfaces.api.composition.persistence import session_limits
from smb_requirement_agent.interfaces.api.composition.projections import (
    refresh_postgres_projections,
)
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
OWNER = {"X-Fake-Actor-Id": "fake-owner"}


@pytest.fixture
def isolated_url() -> Iterator[str]:
    assert DATABASE_URL is not None
    schema = f"session_limits_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    url = f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    run_migrations(url)
    yield url
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def _settings(url: str, **changes: float) -> Settings:
    return Settings(
        llm_provider=LLMProvider.FAKE,
        persistence_provider=PersistenceProvider.POSTGRES,
        database_url=url,
        **changes,  # type: ignore[arg-type]
    )


@pytest.fixture
def store(isolated_url: str) -> Iterator[PostgresStore]:
    settings = _settings(
        isolated_url,
        database_statement_timeout_seconds=0.3,
        database_lock_timeout_seconds=0.2,
        database_idle_transaction_timeout_seconds=0.5,
    )
    connector = PooledPostgresConnector(
        isolated_url,
        min_size=0,
        max_size=2,
        acquire_timeout_seconds=5,
        max_idle_seconds=60,
        configure=session_limits(settings),
    )
    connector.open()
    yield PostgresStore(connector, PostgresRevisionWriter().capture, refresh_postgres_projections)
    connector.close()


def test_every_pooled_session_carries_the_limits(store: PostgresStore) -> None:
    with store.connection() as connection:
        shown = [
            connection.execute(f"SHOW {name}").fetchone()
            for name in ("statement_timeout", "lock_timeout", "idle_in_transaction_session_timeout")
        ]
    assert shown == [("300ms",), ("200ms",), ("500ms",)]


def test_a_statement_past_its_limit_is_a_busy_database(store: PostgresStore) -> None:
    with pytest.raises(DatabaseBusyError), store.connection() as connection:
        connection.execute("SELECT pg_sleep(2)")


def test_a_requirement_lock_held_too_long_is_a_busy_database(store: PostgresStore) -> None:
    requirement_id = RequirementId(str(uuid.uuid4()))
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as holder:
        holder.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (requirement_id.value,)
        )
        started = time.monotonic()
        with pytest.raises(DatabaseBusyError), store.transaction():
            store.lock_requirement(requirement_id)
        assert time.monotonic() - started < 3


def test_a_transaction_left_idle_too_long_loses_its_session(isolated_url: str) -> None:
    settings = _settings(isolated_url, database_idle_transaction_timeout_seconds=0.3)
    connector = PooledPostgresConnector(
        isolated_url,
        min_size=0,
        max_size=1,
        acquire_timeout_seconds=5,
        max_idle_seconds=60,
        configure=session_limits(settings),
    )
    connector.open()
    try:
        connection = connector.acquire()
        connection.execute("SELECT 1")
        time.sleep(0.8)
        with pytest.raises(psycopg.errors.IdleInTransactionSessionTimeout):
            connection.execute("SELECT 1")
        connector.release(connection)
        # The pool replaces the ended session.
        with connector.connection() as fresh:
            assert fresh.execute("SELECT 1").fetchone() == (1,)
    finally:
        connector.close()


def test_the_api_answers_503_while_a_table_is_locked_and_reports_its_pool(
    isolated_url: str,
) -> None:
    container = build_container(replace(_settings(isolated_url), database_lock_timeout_seconds=0.3))
    with TestClient(create_app(lambda: container)) as client:
        created = client.post(
            "/requirements",
            json={"title": "Busy", "description": "A table locked by maintenance."},
            headers=OWNER,
        )
        assert created.status_code == 201, created.text
        with psycopg.connect(isolated_url) as holder:
            holder.execute("LOCK TABLE requirements IN ACCESS EXCLUSIVE MODE")
            refused = client.get(f"/requirements/{created.json()['id']}", headers=OWNER)
        assert refused.status_code == 503
        assert refused.json()["code"] == "database_busy"
        assert client.get(f"/requirements/{created.json()['id']}", headers=OWNER).status_code == 200

        exposed = generate_latest(container.metrics.registry).decode()
    assert 'smb_db_pool_connections{state="idle"}' in exposed
    assert "smb_db_pool_max_connections 20.0" in exposed
