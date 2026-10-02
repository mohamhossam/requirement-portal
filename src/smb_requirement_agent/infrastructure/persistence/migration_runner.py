"""Minimal ordered PostgreSQL migration runner."""

from __future__ import annotations

from pathlib import Path

import psycopg

from smb_requirement_agent.application.errors import PersistenceError

MIGRATIONS = Path(__file__).with_name("migrations")
LEGACY_MIGRATION_NAMES = {
    "025_architecture_knowledge.sql": "006_architecture_knowledge.sql",
    "026_immutable_evidence_and_documents.sql": "007_immutable_evidence_and_documents.sql",
}


def latest_packaged_migration() -> str:
    """The migration a fully upgraded database has applied last.

    Readiness compares against this rather than a hard-coded name, so adding a
    migration cannot leave probes accepting a schema that lacks it.
    """
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    if not names:
        raise PersistenceError("No packaged PostgreSQL migrations were found.")
    return names[-1]


def run_migrations(database_url: str) -> None:
    """Apply each packaged SQL migration exactly once."""
    try:
        with psycopg.connect(database_url) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version text PRIMARY KEY,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            applied = {
                row[0]
                for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
            }
            for path in sorted(MIGRATIONS.glob("*.sql")):
                if path.name in applied:
                    continue
                legacy_name = LEGACY_MIGRATION_NAMES.get(path.name)
                if legacy_name in applied:
                    connection.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,)
                    )
                    applied.add(path.name)
                    continue
                connection.execute(path.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,)
                )
    except psycopg.Error as exc:
        raise PersistenceError(f"PostgreSQL migration failed: {exc}") from exc
