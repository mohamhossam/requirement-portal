"""Corpus membership, the corpus actions' audit trail and bulk re-marking (Knowledge Center B3).

PostgreSQL's trigger on `requirement_corpus_membership` marks the Requirement for indexing
again whenever its membership changes; the memory store calls the same hook itself.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from threading import RLock
from typing import Any

from psycopg.types.json import Jsonb

from smb_requirement_agent.domain.knowledge.membership import (
    CorpusAction,
    CorpusMembership,
    CorpusState,
)
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorSnapshot,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

_MEMBERSHIP = (
    "SELECT requirement_id, state, reason, actor_id, actor_name, changed_at "
    "FROM requirement_corpus_membership"
)


def _membership(row: tuple[Any, ...]) -> CorpusMembership:
    return CorpusMembership(
        RequirementId(str(row[0])),
        CorpusState(str(row[1])),
        str(row[2]),
        ActorSnapshot(ActorId(str(row[3])), str(row[4])),
        row[5],
    )


class PostgresCorpusMembership:
    """Read and written inside the corpus action's transaction."""

    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def get(self, requirement_id: RequirementId) -> CorpusMembership | None:
        with self._store.connection() as connection:
            row: tuple[Any, ...] | None = connection.execute(
                f"{_MEMBERSHIP} WHERE requirement_id=%s", (requirement_id.value,)
            ).fetchone()
        return _membership(row) if row is not None else None

    def retired(self) -> dict[str, CorpusMembership]:
        with self._store.connection() as connection:
            rows: list[tuple[Any, ...]] = connection.execute(
                f"{_MEMBERSHIP} WHERE state='retired'"
            ).fetchall()
        return {str(row[0]): _membership(row) for row in rows}

    def save(self, membership: CorpusMembership) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "INSERT INTO requirement_corpus_membership "
                "(requirement_id, state, reason, actor_id, actor_name, changed_at) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (requirement_id) DO UPDATE SET state=EXCLUDED.state, "
                "reason=EXCLUDED.reason, actor_id=EXCLUDED.actor_id, "
                "actor_name=EXCLUDED.actor_name, changed_at=EXCLUDED.changed_at",
                (
                    membership.requirement_id.value,
                    membership.state.value,
                    membership.reason,
                    membership.actor.id.value,
                    membership.actor.display_name,
                    membership.changed_at,
                ),
            )


class PostgresCorpusActions:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def add(self, action: CorpusAction) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "INSERT INTO knowledge_corpus_actions "
                "(action_id, kind, requirement_ids, actor_id, actor_name, reason, acted_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    action.action_id,
                    action.kind.value,
                    Jsonb([item.value for item in action.requirement_ids]),
                    action.actor.id.value,
                    action.actor.display_name,
                    action.reason,
                    action.acted_at,
                ),
            )


class PostgresSourceChanges:
    """Marks Requirements for indexing again, as the triggers do for an edit."""

    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def mark_changed(self, requirement_ids: tuple[RequirementId, ...]) -> int:
        if not requirement_ids:
            return 0
        with self._store.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO knowledge_source_changes (requirement_id) "
                "SELECT requirement_id FROM requirements WHERE requirement_id = ANY(%s) "
                "ON CONFLICT (requirement_id) DO UPDATE "
                "SET change_number=knowledge_source_changes.change_number+1, dirty=true",
                ([item.value for item in requirement_ids],),
            )
            return max(cursor.rowcount, 0)


class InMemoryCorpusMembership:
    def __init__(self, lock: RLock, source_changed: Callable[[RequirementId], None]) -> None:
        self._lock = lock
        self._source_changed = source_changed
        self._memberships: dict[RequirementId, CorpusMembership] = {}

    def snapshot_state(self) -> Any:
        with self._lock:
            return deepcopy(self._memberships)

    def restore_state(self, state: Any) -> None:
        with self._lock:
            self._memberships = deepcopy(state)

    def get(self, requirement_id: RequirementId) -> CorpusMembership | None:
        with self._lock:
            return self._memberships.get(requirement_id)

    def retired(self) -> dict[str, CorpusMembership]:
        with self._lock:
            return {key.value: item for key, item in self._memberships.items() if item.retired}

    def save(self, membership: CorpusMembership) -> None:
        with self._lock:
            self._memberships[membership.requirement_id] = membership
        self._source_changed(membership.requirement_id)


class InMemoryCorpusActions:
    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self.actions: list[CorpusAction] = []

    def snapshot_state(self) -> Any:
        with self._lock:
            return deepcopy(self.actions)

    def restore_state(self, state: Any) -> None:
        with self._lock:
            self.actions = deepcopy(state)

    def add(self, action: CorpusAction) -> None:
        with self._lock:
            self.actions.append(action)


class InMemorySourceChanges:
    def __init__(
        self,
        exists: Callable[[RequirementId], bool],
        source_changed: Callable[[RequirementId], None],
    ) -> None:
        self._exists = exists
        self._source_changed = source_changed

    def mark_changed(self, requirement_ids: tuple[RequirementId, ...]) -> int:
        marked = 0
        for requirement_id in dict.fromkeys(requirement_ids):
            if self._exists(requirement_id):
                self._source_changed(requirement_id)
                marked += 1
        return marked
