"""The migration runner applies each migration once, in order, and fails loudly.

The shared test database already has every packaged migration, so the apply
path is exercised here against a throwaway schema (`search_path`) and a
stand-in migrations folder. The real schema is never touched.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

import psycopg
import pytest

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.infrastructure.persistence import migration_runner

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")


@pytest.fixture
def isolated_url() -> Iterator[str]:
    assert DATABASE_URL is not None
    schema = f"migrations_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    yield f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema}')}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def _migrations(folder: Path, files: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    for name, sql in files.items():
        (folder / name).write_text(sql, encoding="utf-8")
    monkeypatch.setattr(migration_runner, "MIGRATIONS", folder)


def _applied(url: str) -> list[str]:
    with psycopg.connect(url) as connection:
        rows = connection.execute("SELECT version FROM schema_migrations ORDER BY version")
        return [str(row[0]) for row in rows.fetchall()]


def test_migrations_apply_once_in_name_order(
    isolated_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _migrations(
        tmp_path,
        {
            # Applied by name order, not file creation order: 002 needs 001's table.
            "002_add_column.sql": "ALTER TABLE thing ADD COLUMN label text;",
            "001_create.sql": "CREATE TABLE thing (id int PRIMARY KEY);",
        },
        monkeypatch,
    )

    migration_runner.run_migrations(isolated_url)
    migration_runner.run_migrations(isolated_url)  # a second run applies nothing

    assert _applied(isolated_url) == ["001_create.sql", "002_add_column.sql"]
    assert migration_runner.latest_packaged_migration() == "002_add_column.sql"


def test_a_renamed_legacy_migration_is_recorded_not_rerun(
    isolated_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    new_name, legacy = next(iter(migration_runner.LEGACY_MIGRATION_NAMES.items()))
    # Rerunning would fail loudly: the statement is invalid on purpose.
    _migrations(tmp_path, {new_name: "THIS IS NOT SQL;"}, monkeypatch)
    with psycopg.connect(isolated_url) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations (version text PRIMARY KEY, "
            "applied_at timestamptz NOT NULL DEFAULT now())"
        )
        connection.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (legacy,))

    migration_runner.run_migrations(isolated_url)

    assert set(_applied(isolated_url)) == {legacy, new_name}


def test_a_failing_migration_is_a_persistence_error_and_applies_nothing(
    isolated_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _migrations(
        tmp_path,
        {"001_create.sql": "CREATE TABLE thing (id int);", "002_broken.sql": "NOT SQL;"},
        monkeypatch,
    )

    with pytest.raises(PersistenceError, match="PostgreSQL migration failed"):
        migration_runner.run_migrations(isolated_url)

    # One transaction: the good migration before the broken one is not kept either.
    with psycopg.connect(isolated_url) as connection:
        exists = connection.execute("SELECT to_regclass('schema_migrations')").fetchone()
    assert exists is not None and exists[0] is None


def test_an_empty_package_has_no_latest_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(migration_runner, "MIGRATIONS", tmp_path)

    with pytest.raises(PersistenceError, match="No packaged"):
        migration_runner.latest_packaged_migration()
