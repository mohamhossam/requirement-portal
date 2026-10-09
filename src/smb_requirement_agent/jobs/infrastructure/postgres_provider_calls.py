"""Provider call counts and token spend in PostgreSQL, shared by every API and worker."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import cast

import psycopg
from smb_kernel.persistence.connector import PostgresConnector

from smb_requirement_agent.application.errors import PersistenceError

# Rows this much older than any window can no longer count toward one.
_FORGOTTEN_AFTER = timedelta(hours=1)


class PostgresProviderCallLog:
    """An exact sliding window per actor: one row per counted call (ADR-0106).

    A transaction-scoped advisory lock serialises one actor's checks across
    processes, so two replicas cannot both admit the call that fills the window.
    """

    def __init__(self, connector: PostgresConnector) -> None:
        self._connector = connector

    def record_unless_full(
        self, actor_key: str, call_id: str, now: datetime, window: timedelta, limit: int
    ) -> datetime | None:
        try:
            with self._connector.connection() as connection:
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"provider-calls:{actor_key}",),
                )
                connection.execute(
                    "DELETE FROM provider_calls WHERE called_at <= %s OR "
                    "(actor_id = %s AND called_at <= %s)",
                    (now - _FORGOTTEN_AFTER, actor_key, now - window),
                )
                row = connection.execute(
                    "SELECT count(*), min(called_at) FROM provider_calls WHERE actor_id = %s",
                    (actor_key,),
                ).fetchone()
                counted = int(cast(int, row[0])) if row else 0
                if row is not None and counted >= limit:
                    return cast(datetime, row[1])
                connection.execute(
                    "INSERT INTO provider_calls (call_id, actor_id, called_at) VALUES (%s, %s, %s)",
                    (call_id, actor_key, now),
                )
        except psycopg.Error as exc:
            raise PersistenceError("Counting the provider call failed.") from exc
        return None

    def remove(self, actor_key: str, call_id: str) -> None:
        try:
            with self._connector.connection() as connection:
                connection.execute(
                    "DELETE FROM provider_calls WHERE actor_id = %s AND call_id = %s",
                    (actor_key, call_id),
                )
        except psycopg.Error as exc:
            raise PersistenceError("Refunding the provider call failed.") from exc


class PostgresProviderSpend:
    def __init__(self, connector: PostgresConnector) -> None:
        self._connector = connector

    def add(self, day: date, tokens: int) -> None:
        try:
            with self._connector.connection() as connection:
                connection.execute(
                    "INSERT INTO provider_token_spend (day, tokens) VALUES (%s, %s) "
                    "ON CONFLICT (day) DO UPDATE SET tokens = provider_token_spend.tokens + "
                    "EXCLUDED.tokens",
                    (day, tokens),
                )
        except psycopg.Error as exc:
            raise PersistenceError("Recording provider token spend failed.") from exc

    def spent(self, day: date) -> int:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    "SELECT tokens FROM provider_token_spend WHERE day = %s", (day,)
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceError("Reading provider token spend failed.") from exc
        return int(cast(int, row[0])) if row else 0
