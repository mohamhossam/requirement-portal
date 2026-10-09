"""Requirement work's local copy of the reference library's citable state (ADR-0099)."""

from __future__ import annotations

from threading import RLock
from typing import cast

from psycopg.types.json import Jsonb

from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.references.domain.reference import ReferenceDocumentState
from smb_requirement_agent.references.infrastructure.knowledge_payloads import (
    reference_document_state_from_payload,
    reference_document_state_to_payload,
)


class InMemoryReferencePublications:
    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self._states: dict[str, tuple[int, ReferenceDocumentState]] = {}
        self._cursor = 0

    def snapshot_state(self) -> object:
        return (dict(self._states), self._cursor)

    def restore_state(self, state: object) -> None:
        states, cursor = cast(tuple[dict[str, tuple[int, ReferenceDocumentState]], int], state)
        self._states, self._cursor = states, cursor

    def lock(self, document_ids: tuple[str, ...]) -> None:
        # The surrounding application transaction owns the same graph-wide RLock.
        with self._lock:
            pass

    def get(self, document_id: str) -> ReferenceDocumentState | None:
        with self._lock:
            stored = self._states.get(document_id)
            return stored[1] if stored else None

    def apply(self, seq: int, state: ReferenceDocumentState) -> None:
        with self._lock:
            stored = self._states.get(state.document_id)
            if stored is None or seq > stored[0]:
                self._states[state.document_id] = (seq, state)

    def cursor(self) -> int:
        with self._lock:
            return self._cursor

    def advance(self, seq: int) -> None:
        with self._lock:
            self._cursor = max(self._cursor, seq)


class PostgresReferencePublications:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def lock(self, document_ids: tuple[str, ...]) -> None:
        if not document_ids:
            return
        with self._store.connection() as connection:
            connection.execute(
                "SELECT document_id FROM reference_publication_state "
                "WHERE document_id = ANY(%s) ORDER BY document_id FOR SHARE",
                (list(document_ids),),
            )

    def get(self, document_id: str) -> ReferenceDocumentState | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM reference_publication_state WHERE document_id = %s",
                (document_id,),
            ).fetchone()
        return reference_document_state_from_payload(row[0]) if row else None

    def apply(self, seq: int, state: ReferenceDocumentState) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "INSERT INTO reference_publication_state (document_id, seq, payload) "
                "VALUES (%s, %s, %s) ON CONFLICT (document_id) DO UPDATE "
                "SET seq = excluded.seq, payload = excluded.payload "
                "WHERE excluded.seq > reference_publication_state.seq",
                (state.document_id, seq, Jsonb(reference_document_state_to_payload(state))),
            )

    def cursor(self) -> int:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT seq FROM knowledge_event_cursors WHERE consumer = 'reference_publications'"
            ).fetchone()
        return int(cast(int, row[0])) if row else 0

    def advance(self, seq: int) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "INSERT INTO knowledge_event_cursors (consumer, seq) "
                "VALUES ('reference_publications', %s) ON CONFLICT (consumer) DO UPDATE "
                "SET seq = GREATEST(knowledge_event_cursors.seq, excluded.seq)",
                (seq,),
            )
