"""Approved backlogs on their way to the knowledge service (ADR-0101 Amendment 2).

The in-memory outbox joins memory transactions, and the Postgres one joins the caller's
transaction, so a handoff is queued with the approval or not at all.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from threading import RLock
from typing import cast

from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.references.application.ports.knowledge_handoff import BacklogHandoff

_CHANGED = "The approved-backlog handoff changed. Claim it again."


def _advances(handoff: BacklogHandoff, expected_version: int) -> None:
    if handoff.version != expected_version + 1:
        raise PersistenceError("An approved-backlog handoff advances one version at a time.")


class InMemoryBacklogHandoffs:
    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self._handoffs: dict[str, BacklogHandoff] = {}

    def snapshot_state(self) -> object:
        return dict(self._handoffs)

    def restore_state(self, state: object) -> None:
        self._handoffs = cast(dict[str, BacklogHandoff], state)

    def enqueue(self, handoff: BacklogHandoff) -> bool:
        with self._lock:
            if handoff.approval_id in self._handoffs:
                return False
            self._handoffs[handoff.approval_id] = handoff
            return True

    def get(self, approval_id: str) -> BacklogHandoff | None:
        with self._lock:
            return self._handoffs.get(approval_id)

    def claim(self, now: datetime, lease: timedelta, token: str) -> BacklogHandoff | None:
        with self._lock:
            due = sorted(
                (item for item in self._handoffs.values() if item.due(now)),
                key=lambda item: (item.next_attempt_at, item.approval_id),
            )
            if not due:
                return None
            claimed = due[0].leased(token, now + lease)
            self.save(claimed, due[0].version)
            return claimed

    def save(self, handoff: BacklogHandoff, expected_version: int) -> None:
        _advances(handoff, expected_version)
        with self._lock:
            previous = self._handoffs.get(handoff.approval_id)
            if previous is None or previous.version != expected_version:
                raise PersistenceError(_CHANGED)
            self._handoffs[handoff.approval_id] = handoff


class PostgresBacklogHandoffs:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store
        self._codec = TypeAdapter(BacklogHandoff)

    def _dump(self, handoff: BacklogHandoff) -> Jsonb:
        return Jsonb(self._codec.dump_python(handoff, mode="json"))

    def enqueue(self, handoff: BacklogHandoff) -> bool:
        with self._store.connection() as connection:
            result = connection.execute(
                """INSERT INTO approved_backlog_handoffs
                (approval_id, requirement_id, status, next_attempt_at, lease_until, version,
                 payload, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (approval_id) DO NOTHING""",
                (
                    handoff.approval_id,
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

    def get(self, approval_id: str) -> BacklogHandoff | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM approved_backlog_handoffs WHERE approval_id=%s",
                (approval_id,),
            ).fetchone()
        return self._codec.validate_python(row[0]) if row else None

    def claim(self, now: datetime, lease: timedelta, token: str) -> BacklogHandoff | None:
        with self._store.transaction(), self._store.connection() as connection:
            row = connection.execute(
                """SELECT payload FROM approved_backlog_handoffs
                WHERE status='pending' AND next_attempt_at <= %s
                AND (lease_until IS NULL OR lease_until <= %s)
                ORDER BY next_attempt_at, approval_id
                FOR UPDATE SKIP LOCKED LIMIT 1""",
                (now, now),
            ).fetchone()
            if not row:
                return None
            previous = self._codec.validate_python(row[0])
            claimed = previous.leased(token, now + lease)
            self.save(claimed, previous.version)
            return claimed

    def save(self, handoff: BacklogHandoff, expected_version: int) -> None:
        _advances(handoff, expected_version)
        with self._store.connection() as connection:
            result = connection.execute(
                """UPDATE approved_backlog_handoffs
                SET status=%s, next_attempt_at=%s, lease_until=%s, version=%s, payload=%s,
                    updated_at=now()
                WHERE approval_id=%s AND version=%s""",
                (
                    handoff.status.value,
                    handoff.next_attempt_at,
                    handoff.lease_until,
                    handoff.version,
                    self._dump(handoff),
                    handoff.approval_id,
                    expected_version,
                ),
            )
            if result.rowcount != 1:
                raise PersistenceError(_CHANGED)
