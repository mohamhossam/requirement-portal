"""Focused PostgreSQL persistence adapter."""

from __future__ import annotations

from psycopg.types.json import Jsonb

from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import (
    _payload,
)
from smb_requirement_agent.requirements.application.errors import DocumentVersionConflictError
from smb_requirement_agent.requirements.domain.document.entities import SourceDocument
from smb_requirement_agent.requirements.domain.document.value_objects import DocumentId
from smb_requirement_agent.requirements.infrastructure.document_payloads import (
    document_from_payload,
    document_to_payload,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class PostgresDocumentRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def add(self, document: SourceDocument) -> None:
        with self._store.connection() as connection:
            connection.execute(
                """
                INSERT INTO source_documents (document_id, requirement_id, draft_id, payload)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    document.id.value,
                    document.requirement_id.value if document.requirement_id else None,
                    document.draft_id.value if document.draft_id else None,
                    Jsonb(document_to_payload(document)),
                ),
            )
            if document.requirement_id is not None:
                self._store.mark_requirement_dirty(document.requirement_id)

    def get(self, document_id: DocumentId) -> SourceDocument | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM source_documents WHERE document_id = %s",
                (document_id.value,),
            ).fetchone()
        return document_from_payload(_payload(row[0])) if row is not None else None

    def save(self, document: SourceDocument) -> None:
        with self._store.connection() as connection:
            payload = Jsonb(document_to_payload(document))
            result = connection.execute(
                """
                UPDATE source_documents
                SET requirement_id = %s, draft_id = %s, payload = %s, updated_at = now()
                WHERE document_id = %s
                  AND ((payload->>'version_number')::integer = %s OR payload = %s)
                """,
                (
                    document.requirement_id.value if document.requirement_id else None,
                    document.draft_id.value if document.draft_id else None,
                    payload,
                    document.id.value,
                    document.version_number - 1,
                    payload,
                ),
            )
            if result.rowcount != 1:
                raise DocumentVersionConflictError(
                    "The document changed before this mutation could be saved. Reload it."
                )
            if document.requirement_id is not None:
                self._store.mark_requirement_dirty(document.requirement_id)

    def list_documents(
        self,
        *,
        requirement_id: RequirementId | None = None,
        draft_id: RequirementId | None = None,
    ) -> list[SourceDocument]:
        clauses = ["(payload->>'removed')::boolean = false"]
        parameters: list[str] = []
        if requirement_id is not None:
            clauses.append("requirement_id = %s")
            parameters.append(requirement_id.value)
        if draft_id is not None:
            clauses.append("draft_id = %s")
            parameters.append(draft_id.value)
        query = (
            "SELECT payload FROM source_documents WHERE "  # noqa: S608 - constant fragments; values are parameters
            + " AND ".join(clauses)
            + " ORDER BY updated_at DESC"
        )
        with self._store.connection() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()
        return [document_from_payload(_payload(row[0])) for row in rows]

    def list_all(self) -> list[SourceDocument]:
        return self.list_documents()

    def list_for_requirement(self, requirement_id: RequirementId) -> list[SourceDocument]:
        return self.list_documents(requirement_id=requirement_id)

    def list_for_draft(self, draft_id: RequirementId) -> list[SourceDocument]:
        return self.list_documents(draft_id=draft_id)
