"""Decided product verdicts on their way to the knowledge service (ontology plan Phase 5).

The in-memory outbox joins memory transactions, and the Postgres one joins the caller's
transaction, so a decision is queued with the decision or not at all.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from threading import RLock
from typing import cast

from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.references.application.ports.precedent_handoff import (
    PrecedentHandoff,
)

_CHANGED = "The decided-verdict handoff changed. Claim it again."


def _advances(handoff: PrecedentHandoff, expected_version: int) -> None:
    if handoff.version != expected_version + 1:
        raise PersistenceError("A decided-verdict handoff advances one version at a time.")


class InMemoryPrecedentHandoffs:
    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self._handoffs: dict[str, PrecedentHandoff] = {}

    def snapshot_state(self) -> object:
        return dict(self._handoffs)

    def restore_state(self, state: object) -> None:
        self._handoffs = cast(dict[str, PrecedentHandoff], state)

    def enqueue(self, handoff: PrecedentHandoff) -> bool:
        with self._lock:
            if handoff.handoff_id in self._handoffs:
                return False
            self._handoffs[handoff.handoff_id] = handoff
            return True

    def get(self, handoff_id: str) -> PrecedentHandoff | None:
        with self._lock:
            return self._handoffs.get(handoff_id)

    def claim(self, now: datetime, lease: timedelta, token: str) -> PrecedentHandoff | None:
        with self._lock:
            due = sorted(
                (item for item in self._handoffs.values() if item.due(now)),
                key=lambda item: (item.next_attempt_at, item.handoff_id),
            )
            if not due:
                return None
            claimed = due[0].leased(token, now + lease)
            self.save(claimed, due[0].version)
            return claimed

    def save(self, handoff: PrecedentHandoff, expected_version: int) -> None:
        _advances(handoff, expected_version)
        with self._lock:
            previous = self._handoffs.get(handoff.handoff_id)
            if previous is None or previous.version != expected_version:
                raise PersistenceError(_CHANGED)
            self._handoffs[handoff.handoff_id] = handoff


class PostgresPrecedentHandoffs:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store
        self._codec = TypeAdapter(PrecedentHandoff)

    def _dump(self, handoff: PrecedentHandoff) -> Jsonb:
        return Jsonb(self._codec.dump_python(handoff, mode="json"))

    def enqueue(self, handoff: PrecedentHandoff) -> bool:
        with self._store.connection() as connection:
            result = connection.execute(
                """INSERT INTO precedent_handoffs
                (handoff_id, requirement_id, status, next_attempt_at, lease_until, version,
                 payload, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (handoff_id) DO NOTHING""",
                (
                    handoff.handoff_id,
                    handoff.requirement_id,
                    handoff.status.value,
                    handoff.next_attempt_at,
                    handoff.lease_until,
                    handoff.version,
                    self._dump(handoff),
                    handoff.created_at,
                ),
            )
            return result.rowcount == 1

    def get(self, handoff_id: str) -> PrecedentHandoff | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM precedent_handoffs WHERE handoff_id=%s", (handoff_id,)
            ).fetchone()
        return self._codec.validate_python(row[0]) if row else None

    def claim(self, now: datetime, lease: timedelta, token: str) -> PrecedentHandoff | None:
        with self._store.transaction(), self._store.connection() as connection:
            row = connection.execute(
                """SELECT payload FROM precedent_handoffs
                WHERE status='pending' AND next_attempt_at <= %s
                AND (lease_until IS NULL OR lease_until <= %s)
                ORDER BY next_attempt_at, handoff_id
                FOR UPDATE SKIP LOCKED LIMIT 1""",
                (now, now),
            ).fetchone()
            if not row:
                return None
            previous = self._codec.validate_python(row[0])
            claimed = previous.leased(token, now + lease)
            self.save(claimed, previous.version)
            return claimed

    def save(self, handoff: PrecedentHandoff, expected_version: int) -> None:
        _advances(handoff, expected_version)
        with self._store.connection() as connection:
            result = connection.execute(
                """UPDATE precedent_handoffs
                SET status=%s, next_attempt_at=%s, lease_until=%s, version=%s, payload=%s,
                    updated_at=now()
                WHERE handoff_id=%s AND version=%s""",
                (
                    handoff.status.value,
                    handoff.next_attempt_at,
                    handoff.lease_until,
                    handoff.version,
                    self._dump(handoff),
                    handoff.handoff_id,
                    expected_version,
                ),
            )
            if result.rowcount != 1:
                raise PersistenceError(_CHANGED)
