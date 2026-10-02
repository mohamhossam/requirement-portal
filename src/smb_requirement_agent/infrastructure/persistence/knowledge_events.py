"""The knowledge side's event outbox, written with the change each event reports (ADR-0099)."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from typing import cast

from psycopg.types.json import Jsonb

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.application.ports.knowledge_events import KnowledgeEvent
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession


class InMemoryKnowledgeEvents:
    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self._events: list[KnowledgeEvent] = []

    def snapshot_state(self) -> object:
        return list(self._events)

    def restore_state(self, state: object) -> None:
        self._events = cast(list[KnowledgeEvent], state)

    def append(self, kind: str, subject_id: str, payload: object) -> int:
        with self._lock:
            seq = len(self._events) + 1
            self._events.append(KnowledgeEvent(seq, kind, subject_id, payload, datetime.now(UTC)))
            return seq

    def after(self, seq: int, limit: int) -> tuple[KnowledgeEvent, ...]:
        with self._lock:
            return tuple(e for e in self._events if e.seq > seq)[:limit]


class PostgresKnowledgeEvents:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def append(self, kind: str, subject_id: str, payload: object) -> int:
        with self._store.connection() as connection:
            row = connection.execute(
                "INSERT INTO knowledge_events (kind, subject_id, payload) "
                "VALUES (%s, %s, %s) RETURNING seq",
                (kind, subject_id, Jsonb(payload)),
            ).fetchone()
        if row is None or not isinstance(row[0], int):
            raise PersistenceError("Knowledge event was not recorded.")
        return row[0]

    def after(self, seq: int, limit: int) -> tuple[KnowledgeEvent, ...]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT seq, kind, subject_id, payload, created_at FROM knowledge_events "
                "WHERE seq > %s ORDER BY seq LIMIT %s",
                (seq, limit),
            ).fetchall()
        return tuple(
            KnowledgeEvent(int(cast(int, r[0])), str(r[1]), str(r[2]), r[3], cast(datetime, r[4]))
            for r in rows
        )
