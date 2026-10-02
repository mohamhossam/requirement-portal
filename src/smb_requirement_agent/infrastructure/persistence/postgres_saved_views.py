"""PostgreSQL saved-view adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from smb_requirement_agent.application.errors import (
    InvalidSavedViewError,
    PersistenceError,
    SavedViewConflictError,
)
from smb_requirement_agent.application.ports.requirement_worklist import (
    WorkflowStatus,
    WorklistSort,
)
from smb_requirement_agent.application.ports.saved_views import (
    SavedRequirementView,
    SavedViewCriteria,
)
from smb_requirement_agent.domain.identity.entities import ActorId
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession


class PostgresSavedViewRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def list_for_actor(self, actor_id: ActorId) -> list[SavedRequirementView]:
        with self._store.connection() as connection:
            rows = connection.execute(
                """
                SELECT view_id,actor_id,name,criteria,version,created_at,updated_at
                FROM saved_requirement_views WHERE actor_id=%s ORDER BY lower(name),view_id
                """,
                (actor_id.value,),
            ).fetchall()
        return [_view(row) for row in rows]

    def get(self, view_id: str) -> SavedRequirementView | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """
                SELECT view_id,actor_id,name,criteria,version,created_at,updated_at
                FROM saved_requirement_views WHERE view_id=%s
                """,
                (view_id,),
            ).fetchone()
        return _view(row) if row is not None else None

    def add(self, view: SavedRequirementView) -> None:
        with self._store.connection() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO saved_requirement_views
                        (view_id,actor_id,name,criteria,version,created_at,updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        view.id,
                        view.actor_id.value,
                        view.name,
                        Jsonb(_criteria_payload(view.criteria)),
                        view.version,
                        view.created_at,
                        view.updated_at,
                    ),
                )
            except UniqueViolation as exc:
                raise SavedViewConflictError("A saved view with this name already exists.") from exc

    def save(self, view: SavedRequirementView, expected_version: int) -> None:
        with self._store.connection() as connection:
            try:
                cursor = connection.execute(
                    """
                    UPDATE saved_requirement_views
                    SET name=%s,criteria=%s,version=%s,updated_at=%s
                    WHERE view_id=%s AND version=%s
                    """,
                    (
                        view.name,
                        Jsonb(_criteria_payload(view.criteria)),
                        view.version,
                        view.updated_at,
                        view.id,
                        expected_version,
                    ),
                )
            except UniqueViolation as exc:
                raise SavedViewConflictError("A saved view with this name already exists.") from exc
            if cursor.rowcount != 1:
                raise SavedViewConflictError("The saved view changed since it was loaded.")

    def delete(self, view_id: str, expected_version: int) -> None:
        with self._store.connection() as connection:
            cursor = connection.execute(
                "DELETE FROM saved_requirement_views WHERE view_id=%s AND version=%s",
                (view_id, expected_version),
            )
            if cursor.rowcount != 1:
                raise SavedViewConflictError("The saved view changed since it was loaded.")

    def name_exists(self, actor_id: ActorId, name: str, *, excluding_id: str | None = None) -> bool:
        with self._store.connection() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM saved_requirement_views
                WHERE actor_id=%s AND lower(name)=lower(%s) AND (%s IS NULL OR view_id<>%s)
                """,
                (actor_id.value, name.strip(), excluding_id, excluding_id),
            ).fetchone()
        return row is not None


def _criteria_payload(criteria: SavedViewCriteria) -> dict[str, object]:
    return {
        "query": criteria.query,
        "workflow_statuses": [item.value for item in criteria.workflow_statuses],
        "sort": criteria.sort.value,
        "owner_id": criteria.owner_id.value if criteria.owner_id else None,
        "assigned_to_me": criteria.assigned_to_me,
    }


def _view(row: Any) -> SavedRequirementView:
    try:
        payload = row[3]
        if not isinstance(payload, dict):
            raise TypeError("criteria must be a JSON object")
        owner = payload.get("owner_id")
        statuses = payload.get("workflow_statuses", [])
        if not isinstance(statuses, list):
            raise TypeError("workflow_statuses must be an array")
        return SavedRequirementView(
            str(row[0]),
            ActorId(str(row[1])),
            str(row[2]),
            SavedViewCriteria(
                str(payload["query"]) if payload.get("query") else None,
                tuple(WorkflowStatus(str(item)) for item in statuses),
                WorklistSort(str(payload.get("sort", WorklistSort.UPDATED_DESC.value))),
                ActorId(str(owner)) if owner else None,
                bool(payload.get("assigned_to_me", False)),
            ),
            int(row[4]),
            _datetime(row[5]),
            _datetime(row[6]),
        )
    except (InvalidSavedViewError, KeyError, TypeError, ValueError) as exc:
        raise PersistenceError("Stored saved-view content is invalid.") from exc


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("saved-view timestamp must be a datetime")
    return value
