"""Requirement work's local copy of which catalogue release is active (ADR-0099)."""

from __future__ import annotations

from threading import RLock
from typing import cast

from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.references.application.ports.architecture_knowledge import ActiveRelease


class InMemoryArchitectureReleaseState:
    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self._current: tuple[int, ActiveRelease] | None = None

    def snapshot_state(self) -> object:
        return self._current

    def restore_state(self, state: object) -> None:
        self._current = cast(tuple[int, ActiveRelease] | None, state)

    def active_release_id(self) -> str | None:
        release = self.active_release()
        return release.id if release else None

    def active_release(self) -> ActiveRelease | None:
        with self._lock:
            return self._current[1] if self._current else None

    def apply(self, seq: int, release: ActiveRelease) -> None:
        with self._lock:
            if self._current is None or seq > self._current[0]:
                self._current = (seq, release)


class PostgresArchitectureReleaseState:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def active_release_id(self) -> str | None:
        release = self.active_release()
        return release.id if release else None

    def active_release(self) -> ActiveRelease | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT release_id, name FROM active_architecture_release WHERE singleton"
            ).fetchone()
        if row is None:
            return None
        return ActiveRelease(str(row[0]), None if row[1] is None else str(row[1]))

    def apply(self, seq: int, release: ActiveRelease) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "INSERT INTO active_architecture_release (singleton, release_id, name, seq) "
                "VALUES (true, %s, %s, %s) ON CONFLICT (singleton) DO UPDATE "
                "SET release_id = excluded.release_id, name = excluded.name, seq = excluded.seq "
                "WHERE excluded.seq > active_architecture_release.seq",
                (release.id, release.name, seq),
            )
