"""No knowledge table outlives the upgrade (ADR-0099, ADR-0104).

The real migrations run in a throwaway schema standing in for the requirements
database. Every migration but the last two runs first, so the schema is an earlier
system's, still holding the knowledge tables.
"""

from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

import psycopg
import pytest
from psycopg.types.json import Jsonb

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.infrastructure.persistence import migration_runner
from tests.knowledge_tables import (
    DROP_EMPTY_MIGRATION,
    KNOWLEDGE_TABLE_DROPS,
    KNOWLEDGE_TABLES,
    REQUIRE_GONE_MIGRATION,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")

REAL_MIGRATIONS = Path(migration_runner.MIGRATIONS)


def _schema_url(schema: str) -> str:
    assert DATABASE_URL is not None
    separator = "&" if "?" in DATABASE_URL else "?"
    return f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"


@pytest.fixture
def earlier_system(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The URL of a schema migrated up to, but not including, the knowledge table drops."""
    assert DATABASE_URL is not None
    schema = f"req_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    for path in REAL_MIGRATIONS.glob("*.sql"):
        if path.name not in KNOWLEDGE_TABLE_DROPS:
            shutil.copy(path, tmp_path / path.name)
    monkeypatch.setattr(migration_runner, "MIGRATIONS", tmp_path)
    migration_runner.run_migrations(_schema_url(schema))
    yield _schema_url(schema)
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def _tables(url: str) -> set[str]:
    with psycopg.connect(url) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = current_schema()"
            )
        }


def _migrate_to_latest(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(migration_runner, "MIGRATIONS", REAL_MIGRATIONS)
    migration_runner.run_migrations(url)


def test_the_last_two_migrations_are_the_knowledge_table_drops() -> None:
    names = sorted(path.name for path in REAL_MIGRATIONS.glob("*.sql"))
    assert names[-2:] == [DROP_EMPTY_MIGRATION, REQUIRE_GONE_MIGRATION]


@pytest.mark.parametrize("migration", sorted(KNOWLEDGE_TABLE_DROPS))
def test_both_migrations_name_every_knowledge_table(migration: str) -> None:
    text = (REAL_MIGRATIONS / migration).read_text(encoding="utf-8")
    assert all(f"'{table}'" in text for table in KNOWLEDGE_TABLES)


def test_a_fresh_database_has_no_knowledge_table(monkeypatch: pytest.MonkeyPatch) -> None:
    assert DATABASE_URL is not None
    schema = f"fresh_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    try:
        url = _schema_url(schema)
        _migrate_to_latest(url, monkeypatch)

        tables = _tables(url)
        assert not tables & set(KNOWLEDGE_TABLES)
        assert {"requirements", "document_blobs", "requirement_mapping_jobs"} <= tables
    finally:
        with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
            connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def test_upgrading_drops_the_tables_while_every_one_is_empty(
    earlier_system: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _tables(earlier_system)
    assert set(KNOWLEDGE_TABLES) <= before

    _migrate_to_latest(earlier_system, monkeypatch)

    assert _tables(earlier_system) == before - set(KNOWLEDGE_TABLES)


def test_upgrading_stops_while_a_table_holds_rows_and_changes_nothing(
    earlier_system: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with psycopg.connect(earlier_system) as connection:
        connection.execute(
            "INSERT INTO organisation_catalogue (payload) VALUES (%s)",
            (Jsonb({"people": [{"id": "layla"}]}),),
        )
    before = _tables(earlier_system)

    with pytest.raises(PersistenceError) as raised:
        _migrate_to_latest(earlier_system, monkeypatch)

    message = str(raised.value)
    assert "Knowledge tables still hold rows" in message
    assert "organisation_catalogue" in message
    assert '"Knowledge tables left behind"' in message
    # The upgrade runs in one transaction, so the rows and every table are still there.
    assert _tables(earlier_system) == before
    with psycopg.connect(earlier_system) as connection:
        row = connection.execute("SELECT count(*) FROM organisation_catalogue").fetchone()
        assert row == (1,)
