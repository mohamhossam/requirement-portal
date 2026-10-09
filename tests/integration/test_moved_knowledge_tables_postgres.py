"""Dropping the moved knowledge tables on the real schema (ADR-0099).

The real migrations run in a throwaway schema standing in for the requirements
database. Every migration but the one that drops the empty tables runs, so the
schema is an earlier system's, still holding them. A second throwaway schema
stands in for the knowledge database: it holds copies made with `LIKE`, so rows
render the same text on both sides.
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

from smb_requirement_agent.infrastructure.persistence import migration_runner
from smb_requirement_agent.infrastructure.persistence.moved_knowledge_tables import (
    DROP_EMPTY_MIGRATION,
    MOVED_TABLES,
    TableState,
    drop_moved_tables,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")


def _schema_url(schema: str) -> str:
    assert DATABASE_URL is not None
    separator = "&" if "?" in DATABASE_URL else "?"
    return f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"


REAL_MIGRATIONS = Path(migration_runner.MIGRATIONS)


@pytest.fixture
def schemas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, str, str]]:
    """The requirements and knowledge stand-ins: (requirements schema, its URL, knowledge URL)."""
    assert DATABASE_URL is not None
    requirements, knowledge = f"req_{uuid.uuid4().hex}", f"kn_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{requirements}"')
        connection.execute(f'CREATE SCHEMA "{knowledge}"')
    for path in REAL_MIGRATIONS.glob("*.sql"):
        if path.name != DROP_EMPTY_MIGRATION:
            shutil.copy(path, tmp_path / path.name)
    monkeypatch.setattr(migration_runner, "MIGRATIONS", tmp_path)
    migration_runner.run_migrations(_schema_url(requirements))
    yield requirements, _schema_url(requirements), _schema_url(knowledge)
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{requirements}" CASCADE')
        connection.execute(f'DROP SCHEMA "{knowledge}" CASCADE')


def _tables(url: str) -> set[str]:
    with psycopg.connect(url) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = current_schema()"
            )
        }


def _catalogue_row(url: str) -> None:
    with psycopg.connect(url) as connection:
        connection.execute(
            "INSERT INTO organisation_catalogue (payload) VALUES (%s)",
            (Jsonb({"people": [{"id": "layla"}]}),),
        )


def _copy_to_knowledge(requirements: str, knowledge_url: str, *, change: bool = False) -> None:
    with psycopg.connect(knowledge_url) as connection:
        connection.execute(
            f'CREATE TABLE organisation_catalogue (LIKE "{requirements}".organisation_catalogue '
            "INCLUDING ALL)"
        )
        connection.execute(
            "INSERT INTO organisation_catalogue "
            f'SELECT * FROM "{requirements}".organisation_catalogue'
        )
        if change:
            connection.execute(
                "UPDATE organisation_catalogue SET payload = %s", (Jsonb({"people": []}),)
            )


def test_empty_tables_are_all_dropped_and_requirement_work_is_kept(
    schemas: tuple[str, str, str],
) -> None:
    _, url, _ = schemas
    before = _tables(url)
    present = before & set(MOVED_TABLES)
    assert "library_documents" in present and "organisation_catalogue" in present

    result = drop_moved_tables(url)

    assert result.dropped and not result.refused
    after = _tables(url)
    assert not after & set(MOVED_TABLES)
    assert after == before - present
    assert {"requirements", "document_blobs", "requirement_mapping_jobs"} <= after

    again = drop_moved_tables(url)
    assert not again.dropped and not again.refused
    assert {report.state for report in again.reports} == {TableState.ABSENT}


def test_rows_with_no_knowledge_database_to_check_refuse_and_drop_nothing(
    schemas: tuple[str, str, str],
) -> None:
    _, url, _ = schemas
    _catalogue_row(url)
    before = _tables(url)

    result = drop_moved_tables(url)

    assert not result.dropped
    assert [(r.table, r.state, r.rows) for r in result.refused] == [
        ("organisation_catalogue", TableState.NOT_CHECKED, 1)
    ]
    assert _tables(url) == before


def test_rows_the_knowledge_database_lacks_refuse(schemas: tuple[str, str, str]) -> None:
    _, url, knowledge_url = schemas
    _catalogue_row(url)

    result = drop_moved_tables(url, knowledge_url)

    assert [(r.table, r.state) for r in result.refused] == [
        ("organisation_catalogue", TableState.NOT_COPIED)
    ]
    assert "organisation_catalogue" in _tables(url)


def test_a_copy_that_differs_refuses(schemas: tuple[str, str, str]) -> None:
    requirements, url, knowledge_url = schemas
    _catalogue_row(url)
    _copy_to_knowledge(requirements, knowledge_url, change=True)

    result = drop_moved_tables(url, knowledge_url)

    assert [(r.table, r.state) for r in result.refused] == [
        ("organisation_catalogue", TableState.DIFFERS)
    ]
    assert "organisation_catalogue" in _tables(url)


def test_an_identical_copy_lets_the_drop_go_ahead_and_a_dry_run_changes_nothing(
    schemas: tuple[str, str, str],
) -> None:
    requirements, url, knowledge_url = schemas
    _catalogue_row(url)
    _copy_to_knowledge(requirements, knowledge_url)
    before = _tables(url)

    dry = drop_moved_tables(url, knowledge_url, dry_run=True)
    assert not dry.dropped and not dry.refused
    assert _tables(url) == before

    result = drop_moved_tables(url, knowledge_url)

    assert result.dropped
    copied = next(r for r in result.reports if r.table == "organisation_catalogue")
    assert (copied.state, copied.rows) == (TableState.COPIED, 1)
    assert not _tables(url) & set(MOVED_TABLES)
    # The knowledge database is only read.
    assert "organisation_catalogue" in _tables(knowledge_url)


def _migrate_to_latest(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(migration_runner, "MIGRATIONS", REAL_MIGRATIONS)
    migration_runner.run_migrations(url)


def test_a_fresh_database_has_no_moved_table(monkeypatch: pytest.MonkeyPatch) -> None:
    assert DATABASE_URL is not None
    schema = f"fresh_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    try:
        url = _schema_url(schema)
        _migrate_to_latest(url, monkeypatch)

        tables = _tables(url)
        assert not tables & set(MOVED_TABLES)
        assert {"requirements", "document_blobs", "requirement_mapping_jobs"} <= tables
    finally:
        with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
            connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def test_upgrading_drops_the_tables_while_every_one_is_empty(
    schemas: tuple[str, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, url, _ = schemas
    before = _tables(url)

    _migrate_to_latest(url, monkeypatch)

    assert _tables(url) == before - set(MOVED_TABLES)


def test_upgrading_keeps_every_table_while_one_holds_rows(
    schemas: tuple[str, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, url, _ = schemas
    _catalogue_row(url)
    before = _tables(url)

    _migrate_to_latest(url, monkeypatch)

    # Left whole for knowledge-import and the guarded command.
    assert _tables(url) == before
    assert set(MOVED_TABLES) <= before
