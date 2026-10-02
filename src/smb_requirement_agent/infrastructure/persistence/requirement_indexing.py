"""Memory and PostgreSQL Requirement indexing checkpoints; no source text in progress."""

from dataclasses import replace
from datetime import datetime
from threading import RLock

from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.application.ports.requirement_indexing import RequirementIndexProgress
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession


def eligible(progress: RequirementIndexProgress, change: int, now: datetime) -> bool:
    return progress.source_change != change or (
        progress.failures < 3 and (progress.retry_at is None or progress.retry_at <= now)
    )


class MemoryRequirementIndexProgress:
    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self._rows: dict[tuple[str, str], RequirementIndexProgress] = {}
        self._leases: dict[tuple[str, str], tuple[str, datetime]] = {}

    def get(self, identity: str, source: str) -> RequirementIndexProgress:
        with self._lock:
            return self._rows.get((identity, source), RequirementIndexProgress())

    def claim(
        self, identity: str, source: str, change: int, token: str, now: datetime, until: datetime
    ) -> RequirementIndexProgress | None:
        with self._lock:
            key = (identity, source)
            lease = self._leases.get(key)
            progress = self.get(identity, source)
            if (lease and lease[1] > now) or not eligible(progress, change, now):
                return None
            if progress.source_change != change:
                progress = replace(
                    progress, source_change=change, failures=0, retry_at=None, completed=0, total=0
                )
            self._rows[key] = progress
            self._leases[key] = (token, until)
            return progress

    def save(
        self,
        identity: str,
        source: str,
        token: str,
        progress: RequirementIndexProgress,
        now: datetime,
    ) -> bool:
        with self._lock:
            key = (identity, source)
            lease = self._leases.get(key)
            if not lease or lease[0] != token or lease[1] <= now:
                return False
            self._rows[key] = progress
            del self._leases[key]
            return True

    def retry(self, identity: str, source: str, now: datetime) -> bool:
        with self._lock:
            lease = self._leases.get((identity, source))
            if lease and lease[1] > now:
                return False
            self._rows[identity, source] = replace(
                self.get(identity, source),
                failures=0,
                retry_at=None,
            )
            return True


class PostgresRequirementIndexProgress:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store
        self._adapter = TypeAdapter(RequirementIndexProgress)

    def get(self, identity: str, source: str) -> RequirementIndexProgress:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM requirement_index_progress WHERE identity=%s AND source_id=%s",
                (identity, source),
            ).fetchone()
        return self._adapter.validate_python(row[0]) if row else RequirementIndexProgress()

    def claim(
        self, identity: str, source: str, change: int, token: str, now: datetime, until: datetime
    ) -> RequirementIndexProgress | None:
        with self._store.transaction(), self._store.connection() as connection:
            connection.execute(
                "INSERT INTO requirement_index_progress(identity,source_id,payload) "
                "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                (
                    identity,
                    source,
                    Jsonb(self._adapter.dump_python(RequirementIndexProgress(), mode="json")),
                ),
            )
            row = connection.execute(
                "SELECT payload,lease_until FROM requirement_index_progress "
                "WHERE identity=%s AND source_id=%s FOR UPDATE",
                (identity, source),
            ).fetchone()
            if row is None:
                raise PersistenceError("Requirement index progress row disappeared under lock.")
            progress = self._adapter.validate_python(row[0])
            if (isinstance(row[1], datetime) and row[1] > now) or not eligible(
                progress, change, now
            ):
                return None
            if progress.source_change != change:
                progress = replace(
                    progress, source_change=change, failures=0, retry_at=None, completed=0, total=0
                )
            connection.execute(
                "UPDATE requirement_index_progress SET token=%s,lease_until=%s,payload=%s "
                "WHERE identity=%s AND source_id=%s",
                (
                    token,
                    until,
                    Jsonb(self._adapter.dump_python(progress, mode="json")),
                    identity,
                    source,
                ),
            )
            return progress

    def save(
        self,
        identity: str,
        source: str,
        token: str,
        progress: RequirementIndexProgress,
        now: datetime,
    ) -> bool:
        with self._store.connection() as connection:
            cursor = connection.execute(
                "UPDATE requirement_index_progress SET payload=%s,token=NULL,lease_until=NULL "
                "WHERE identity=%s AND source_id=%s AND token=%s AND lease_until>%s",
                (
                    Jsonb(self._adapter.dump_python(progress, mode="json")),
                    identity,
                    source,
                    token,
                    now,
                ),
            )
            return cursor.rowcount == 1

    def retry(self, identity: str, source: str, now: datetime) -> bool:
        with self._store.connection() as connection:
            cursor = connection.execute(
                "UPDATE requirement_index_progress SET "
                'payload=payload || \'{"failures":0,"retry_at":null}\'::jsonb '
                "WHERE identity=%s AND source_id=%s AND (lease_until IS NULL OR lease_until<=%s)",
                (identity, source, now),
            )
            return cursor.rowcount == 1
