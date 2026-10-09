"""PostgreSQL repositories for Requirements and Requirement drafts (ADR-0103 PR 9)."""

from __future__ import annotations

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import _payload
from smb_requirement_agent.requirements.application.errors import (
    DuplicateRequirementError,
    RequirementVersionConflictError,
)
from smb_requirement_agent.requirements.application.ports.requirement_draft_repository import (
    RequirementDraftRepositoryPort,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.domain.requirement.entities import (
    Requirement,
    RequirementDraft,
)
from smb_requirement_agent.requirements.infrastructure.requirement_snapshot import (
    requirement_draft_from_payload,
    requirement_draft_to_payload,
    requirement_from_payload,
    requirement_to_payload,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class PostgresRequirementRepository(RequirementRepositoryPort):
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def add(self, requirement: Requirement) -> None:
        with self._store.connection() as connection:
            try:
                connection.execute(
                    "INSERT INTO requirements (requirement_id, payload) VALUES (%s, %s)",
                    (requirement.id.value, Jsonb(requirement_to_payload(requirement))),
                )
            except UniqueViolation as exc:
                raise DuplicateRequirementError(
                    f"Requirement {requirement.id.value!r} already exists."
                ) from exc
            self._store.mark_requirement_dirty(requirement.id)

    def get(self, requirement_id: RequirementId) -> Requirement | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM requirements WHERE requirement_id = %s",
                (requirement_id.value,),
            ).fetchone()
        return requirement_from_payload(_payload(row[0])) if row is not None else None

    def list_all(self) -> list[Requirement]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM requirements ORDER BY updated_at DESC"
            ).fetchall()
        return [requirement_from_payload(_payload(row[0])) for row in rows]

    def save(self, requirement: Requirement) -> None:
        with self._store.connection() as connection:
            if requirement.version.value > 1:
                cursor = connection.execute(
                    """
                    UPDATE requirements SET payload = %s, updated_at = now()
                    WHERE requirement_id = %s
                    AND COALESCE((payload->>'version')::integer, 1) = %s
                    """,
                    (
                        Jsonb(requirement_to_payload(requirement)),
                        requirement.id.value,
                        requirement.version.value - 1,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RequirementVersionConflictError(
                        f"Requirement {requirement.id.value!r} changed before it could be saved."
                    )
            else:
                connection.execute(
                    """
                    UPDATE requirements SET payload = %s, updated_at = now()
                    WHERE requirement_id = %s
                    """,
                    (Jsonb(requirement_to_payload(requirement)), requirement.id.value),
                )
            self._store.mark_requirement_dirty(requirement.id)


class PostgresRequirementDraftRepository(RequirementDraftRepositoryPort):
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def add(self, draft: RequirementDraft) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "INSERT INTO requirement_drafts (draft_id, payload) VALUES (%s, %s)",
                (draft.id.value, Jsonb(requirement_draft_to_payload(draft))),
            )

    def get(self, draft_id: RequirementId) -> RequirementDraft | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM requirement_drafts WHERE draft_id = %s",
                (draft_id.value,),
            ).fetchone()
        return requirement_draft_from_payload(_payload(row[0])) if row is not None else None

    def list_all(self) -> list[RequirementDraft]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM requirement_drafts ORDER BY updated_at DESC"
            ).fetchall()
        return [requirement_draft_from_payload(_payload(row[0])) for row in rows]

    def save(self, draft: RequirementDraft) -> None:
        with self._store.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE requirement_drafts SET payload = %s, updated_at = now()
                WHERE draft_id = %s AND (payload->>'version')::integer = %s
                """,
                (
                    Jsonb(requirement_draft_to_payload(draft)),
                    draft.id.value,
                    draft.version.value - 1,
                ),
            )
            if cursor.rowcount != 1:
                raise RequirementVersionConflictError(
                    f"Requirement draft {draft.id.value!r} changed before it could be saved."
                )

    def delete(self, draft_id: RequirementId) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "DELETE FROM requirement_drafts WHERE draft_id = %s", (draft_id.value,)
            )
