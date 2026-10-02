"""Requirement work's local copy of which catalogue release is active (ADR-0099)."""

from __future__ import annotations

from threading import RLock
from typing import cast

from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession


class InMemoryArchitectureReleaseState:
    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self._current: tuple[int, str] | None = None

    def snapshot_state(self) -> object:
        return self._current

    def restore_state(self, state: object) -> None:
        self._current = cast(tuple[int, str] | None, state)

    def active_release_id(self) -> str | None:
        with self._lock:
            return self._current[1] if self._current else None

    def apply(self, seq: int, release_id: str) -> None:
        with self._lock:
            if self._current is None or seq > self._current[0]:
                self._current = (seq, release_id)


class PostgresArchitectureReleaseState:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def active_release_id(self) -> str | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT release_id FROM active_architecture_release WHERE singleton"
            ).fetchone()
        return str(row[0]) if row else None

    def apply(self, seq: int, release_id: str) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "INSERT INTO active_architecture_release (singleton, release_id, seq) "
                "VALUES (true, %s, %s) ON CONFLICT (singleton) DO UPDATE "
                "SET release_id = excluded.release_id, seq = excluded.seq "
                "WHERE excluded.seq > active_architecture_release.seq",
                (release_id, seq),
            )
