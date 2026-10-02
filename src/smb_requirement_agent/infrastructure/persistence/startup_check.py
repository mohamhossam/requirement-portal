"""Fast persistence readiness check for the local startup launcher."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from enum import Enum
from urllib.parse import urlsplit

import psycopg

from smb_requirement_agent.infrastructure.config.options import (
    ConfigurationError,
    PersistenceProvider,
)
from smb_requirement_agent.infrastructure.config.settings import PersistenceSettings

CONNECT_TIMEOUT_SECONDS = 3
STATEMENT_TIMEOUT_MILLISECONDS = 3_000


class PersistenceTarget(Enum):
    MEMORY = "memory"
    LOCAL_POSTGRES = "local-postgres"
    EXTERNAL_POSTGRES = "external-postgres"


def classify_persistence(settings: PersistenceSettings) -> PersistenceTarget:
    """Tell launchers whether they may safely start the local Compose service."""
    if settings.provider is PersistenceProvider.MEMORY:
        return PersistenceTarget.MEMORY
    if settings.database_url is None:  # Enforced by PersistenceSettings.
        raise ConfigurationError("PERSISTENCE_PROVIDER=postgres requires DATABASE_URL.")
    hostname = urlsplit(settings.database_url).hostname
    if hostname in {"127.0.0.1", "localhost", "::1"}:
        return PersistenceTarget.LOCAL_POSTGRES
    return PersistenceTarget.EXTERNAL_POSTGRES


def check_persistence(settings: PersistenceSettings) -> None:
    """Verify that configured durable persistence is reachable and usable."""
    if settings.provider is PersistenceProvider.MEMORY:
        return

    if settings.database_url is None:  # Enforced by PersistenceSettings.
        raise ConfigurationError("PERSISTENCE_PROVIDER=postgres requires DATABASE_URL.")
    try:
        with psycopg.connect(
            settings.database_url,
            connect_timeout=CONNECT_TIMEOUT_SECONDS,
            options=f"-c statement_timeout={STATEMENT_TIMEOUT_MILLISECONDS}",
        ) as connection:
            connection.execute("SELECT 1").fetchone()
    except psycopg.Error as exc:
        raise RuntimeError(
            "PostgreSQL is not ready. Start the configured database and verify "
            "DATABASE_URL, or set PERSISTENCE_PROVIDER=memory for offline use."
        ) from exc


def main(argv: Sequence[str] | None = None) -> int:
    """Return a shell-friendly status without exposing connection credentials."""
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    try:
        settings = PersistenceSettings.from_env()
        if "--target" in arguments:
            print(classify_persistence(settings).value)
            return 0
        check_persistence(settings)
    except (ConfigurationError, RuntimeError) as exc:
        if "--quiet" not in arguments:
            print(f"[startup] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
