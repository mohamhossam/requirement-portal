"""Explicit PostgreSQL schema-migration command."""

from __future__ import annotations

import sys

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.infrastructure.config.options import (
    ConfigurationError,
    PersistenceProvider,
)
from smb_requirement_agent.infrastructure.config.settings import PersistenceSettings
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations


def main() -> int:
    """Apply pending migrations independently from the API lifecycle."""
    try:
        settings = PersistenceSettings.from_env()
        if settings.provider is PersistenceProvider.MEMORY:
            print("[migration] No database migrations are required in memory mode.")
            return 0
        if settings.database_url is None:  # Enforced by PersistenceSettings.
            raise ConfigurationError("PERSISTENCE_PROVIDER=postgres requires DATABASE_URL.")
        run_migrations(settings.database_url)
    except (ConfigurationError, PersistenceError) as exc:
        print(f"[migration] {exc}", file=sys.stderr)
        return 1

    print("[migration] PostgreSQL schema is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
