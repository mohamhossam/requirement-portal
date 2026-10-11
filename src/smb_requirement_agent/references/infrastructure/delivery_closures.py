"""Closed and removed Epics on their way to the knowledge service (ontology plan Phase 7).

The in-memory outbox joins memory transactions, and the Postgres one joins the caller's
transaction. Each tracker event is queued once, by its closure id.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from threading import RLock
from typing import cast

from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.references.application.ports.delivery_closure import DeliveryClosure

_CHANGED = "The delivery closure changed. Claim it again."


def _advances(closure: DeliveryClosure, expected_version: int) -> None:
    if closure.version != expected_version + 1:
        raise PersistenceError("A delivery closure advances one version at a time.")


class InMemoryDeliveryClosures:
    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self._closures: dict[str, DeliveryClosure] = {}

    def snapshot_state(self) -> object:
        return dict(self._closures)

    def restore_state(self, state: object) -> None:
        self._closures = cast(dict[str, DeliveryClosure], state)

    def enqueue(self, closure: DeliveryClosure) -> bool:
        with self._lock:
            if closure.closure_id in self._closures:
                return False
            self._closures[closure.closure_id] = closure
            return True

    def get(self, closure_id: str) -> DeliveryClosure | None:
        with self._lock:
            return self._closures.get(closure_id)

    def claim(self, now: datetime, lease: timedelta, token: str) -> DeliveryClosure | None:
        with self._lock:
            due = sorted(
                (item for item in self._closures.values() if item.due(now)),
                key=lambda item: (item.next_attempt_at, item.closure_id),
            )
            if not due:
                return None
            claimed = due[0].leased(token, now + lease)
            self.save(claimed, due[0].version)
            return claimed

    def save(self, closure: DeliveryClosure, expected_version: int) -> None:
        _advances(closure, expected_version)
        with self._lock:
            previous = self._closures.get(closure.closure_id)
            if previous is None or previous.version != expected_version:
                raise PersistenceError(_CHANGED)
            self._closures[closure.closure_id] = closure


class PostgresDeliveryClosures:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store
        self._codec = TypeAdapter(DeliveryClosure)

    def _dump(self, closure: DeliveryClosure) -> Jsonb:
        return Jsonb(self._codec.dump_python(closure, mode="json"))

    def enqueue(self, closure: DeliveryClosure) -> bool:
        with self._store.connection() as connection:
            result = connection.execute(
                """INSERT INTO delivery_closures
                (closure_id, requirement_id, status, next_attempt_at, lease_until, version,
                 payload, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (closure_id) DO NOTHING""",
                (
                    closure.closure_id,
                    closure.requirement_id,
                    closure.status.value,
                    closure.next_attempt_at,
                    closure.lease_until,
                    closure.version,
                    self._dump(closure),
                    closure.created_at,
                ),
            )
            return result.rowcount == 1

    def get(self, closure_id: str) -> DeliveryClosure | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM delivery_closures WHERE closure_id=%s", (closure_id,)
            ).fetchone()
        return self._codec.validate_python(row[0]) if row else None

    def claim(self, now: datetime, lease: timedelta, token: str) -> DeliveryClosure | None:
        with self._store.transaction(), self._store.connection() as connection:
            row = connection.execute(
                """SELECT payload FROM delivery_closures
                WHERE status='pending' AND next_attempt_at <= %s
                AND (lease_until IS NULL OR lease_until <= %s)
                ORDER BY next_attempt_at, closure_id
                FOR UPDATE SKIP LOCKED LIMIT 1""",
                (now, now),
            ).fetchone()
            if not row:
                return None
            previous = self._codec.validate_python(row[0])
            claimed = previous.leased(token, now + lease)
            self.save(claimed, previous.version)
            return claimed

    def save(self, closure: DeliveryClosure, expected_version: int) -> None:
        _advances(closure, expected_version)
        with self._store.connection() as connection:
            result = connection.execute(
                """UPDATE delivery_closures
                SET status=%s, next_attempt_at=%s, lease_until=%s, version=%s, payload=%s,
                    updated_at=now()
                WHERE closure_id=%s AND version=%s""",
                (
                    closure.status.value,
                    closure.next_attempt_at,
                    closure.lease_until,
                    closure.version,
                    self._dump(closure),
                    closure.closure_id,
                    expected_version,
                ),
            )
            if result.rowcount != 1:
                raise PersistenceError(_CHANGED)
