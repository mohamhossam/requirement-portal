"""This application's PostgreSQL migrations, applied by platform-kernel's runner (ADR-0100)."""

from __future__ import annotations

from pathlib import Path

from smb_kernel.persistence import migrations as kernel_migrations

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
    return kernel_migrations.latest_packaged_migration(MIGRATIONS)


def run_migrations(database_url: str) -> None:
    """Apply each packaged SQL migration exactly once."""
    kernel_migrations.run_migrations(database_url, MIGRATIONS, LEGACY_MIGRATION_NAMES)
