"""Durable, version-checked architecture release repository."""

from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb
from pydantic import TypeAdapter, ValidationError
from smb_kernel.persistence.connector import PostgresConnector

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    KnowledgeAuditEvent,
    KnowledgeConflictError,
    KnowledgeDocumentVersion,
    KnowledgeReleaseStatus,
)
from smb_requirement_agent.infrastructure.persistence.postgres_values import _datetime, _integer

_DOCUMENT: TypeAdapter[KnowledgeDocumentVersion] = TypeAdapter(KnowledgeDocumentVersion)

_ADAPTER: TypeAdapter[ArchitectureKnowledge] = TypeAdapter(ArchitectureKnowledge)


class PostgresArchitectureKnowledgeRepository:
    def __init__(self, connector: PostgresConnector, seed: ArchitectureKnowledge) -> None:
        self._connector = connector
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    "SELECT 1 FROM architecture_knowledge_releases LIMIT 1"
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO architecture_knowledge_releases "
                        "(release_id, revision, payload, active) "
                        "VALUES (%s, %s, %s, true) ON CONFLICT DO NOTHING",
                        (seed.id, seed.revision, Jsonb(_ADAPTER.dump_python(seed, mode="json"))),
                    )
        except psycopg.Error as exc:
            raise PersistenceError("Architecture knowledge initialization failed.") from exc

    @staticmethod
    def _release(raw: object) -> ArchitectureKnowledge:
        try:
            return _ADAPTER.validate_python(raw)
        except ValidationError as exc:
            raise PersistenceError("Stored architecture knowledge is invalid.") from exc

    def get(self, release_id: str) -> ArchitectureKnowledge | None:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    "SELECT payload FROM architecture_knowledge_releases WHERE release_id = %s",
                    (release_id,),
                ).fetchone()
            return self._release(row[0]) if row else None
        except psycopg.Error as exc:
            raise PersistenceError("Architecture knowledge read failed.") from exc

    def list_all(self) -> tuple[ArchitectureKnowledge, ...]:
        try:
            with self._connector.connection() as connection:
                rows = connection.execute(
                    "SELECT payload FROM architecture_knowledge_releases ORDER BY created_at DESC"
                ).fetchall()
            return tuple(self._release(row[0]) for row in rows)
        except psycopg.Error as exc:
            raise PersistenceError("Architecture knowledge list failed.") from exc

    def document_versions(self, include_drafts: bool) -> tuple[KnowledgeDocumentVersion, ...]:
        try:
            with self._connector.connection() as connection:
                rows = connection.execute(
                    "SELECT payload FROM architecture_knowledge_documents WHERE published OR %s",
                    (include_drafts,),
                ).fetchall()
            return tuple(_DOCUMENT.validate_python(row[0]) for row in rows)
        except (psycopg.Error, ValidationError) as exc:
            raise PersistenceError("Architecture document list failed.") from exc

    def active(self) -> ArchitectureKnowledge:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    "SELECT payload FROM architecture_knowledge_releases WHERE active"
                ).fetchone()
            if row is None:
                raise PersistenceError("No active architecture release exists.")
            return self._release(row[0])
        except psycopg.Error as exc:
            raise PersistenceError("Active architecture knowledge read failed.") from exc

    def save(
        self,
        release: ArchitectureKnowledge,
        expected_revision: int | None,
        actor_id: str,
        action: str,
    ) -> None:
        payload = Jsonb(_ADAPTER.dump_python(release, mode="json"))
        try:
            with self._connector.connection() as connection:
                if expected_revision is None:
                    row = connection.execute(
                        "INSERT INTO architecture_knowledge_releases "
                        "(release_id, revision, payload) "
                        "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING RETURNING release_id",
                        (release.id, release.revision, payload),
                    ).fetchone()
                else:
                    row = connection.execute(
                        "UPDATE architecture_knowledge_releases SET revision = %s, payload = %s "
                        "WHERE release_id = %s AND revision = %s "
                        "AND payload->>'status' = 'draft' RETURNING release_id",
                        (release.revision, payload, release.id, expected_revision),
                    ).fetchone()
                if row is None:
                    raise KnowledgeConflictError(
                        "The knowledge draft changed; reload before saving."
                    )
                for document in release.documents:
                    connection.execute(
                        "INSERT INTO architecture_knowledge_documents (version_id, payload) "
                        "VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (document.id, Jsonb(_DOCUMENT.dump_python(document, mode="json"))),
                    )
                connection.execute(
                    "INSERT INTO architecture_knowledge_audit "
                    "(release_id, actor_id, action, revision) VALUES (%s, %s, %s, %s)",
                    (release.id, actor_id, action, release.revision),
                )
        except psycopg.Error as exc:
            raise PersistenceError("Architecture knowledge write failed.") from exc

    def audit(self, release_id: str) -> tuple[KnowledgeAuditEvent, ...]:
        try:
            with self._connector.connection() as connection:
                rows = connection.execute(
                    "SELECT release_id, actor_id, action, revision, rationale, created_at "
                    "FROM architecture_knowledge_audit WHERE release_id = %s "
                    "ORDER BY audit_id",
                    (release_id,),
                ).fetchall()
            return tuple(
                KnowledgeAuditEvent(
                    str(row[0]),
                    str(row[1]),
                    str(row[2]),
                    _integer(row[3]),
                    str(row[4]) if row[4] is not None else None,
                    _datetime(row[5]),
                )
                for row in rows
            )
        except psycopg.Error as exc:
            raise PersistenceError("Architecture knowledge audit read failed.") from exc

    def activate(self, release_id: str, actor_id: str, rationale: str) -> None:
        try:
            with self._connector.connection() as connection:
                connection.execute("LOCK TABLE architecture_knowledge_releases IN EXCLUSIVE MODE")
                row = connection.execute(
                    "SELECT payload FROM architecture_knowledge_releases WHERE release_id = %s",
                    (release_id,),
                ).fetchone()
                if (
                    row is None
                    or self._release(row[0]).status is not KnowledgeReleaseStatus.PUBLISHED
                ):
                    raise KnowledgeConflictError("Only a published release can be activated.")
                connection.execute(
                    "UPDATE architecture_knowledge_releases SET active = false WHERE active"
                )
                connection.execute(
                    "UPDATE architecture_knowledge_releases "
                    "SET active = true WHERE release_id = %s",
                    (release_id,),
                )
                release = self._release(row[0])
                connection.execute(
                    "INSERT INTO architecture_knowledge_audit "
                    "(release_id, actor_id, action, revision, rationale) "
                    "VALUES (%s, %s, 'activate', %s, %s)",
                    (release_id, actor_id, release.revision, rationale),
                )
        except psycopg.Error as exc:
            raise PersistenceError("Architecture release activation failed.") from exc

    def publish(
        self, release: ArchitectureKnowledge, expected_revision: int, rationale: str
    ) -> None:
        payload = Jsonb(_ADAPTER.dump_python(release, mode="json"))
        try:
            with self._connector.connection() as connection:
                connection.execute("LOCK TABLE architecture_knowledge_releases IN EXCLUSIVE MODE")
                row = connection.execute(
                    "UPDATE architecture_knowledge_releases SET payload = %s "
                    "WHERE release_id = %s AND revision = %s "
                    "AND payload->>'status' = 'draft' RETURNING release_id",
                    (payload, release.id, expected_revision),
                ).fetchone()
                if row is None:
                    raise KnowledgeConflictError("The draft changed; reload before publishing.")
                connection.execute(
                    "UPDATE architecture_knowledge_releases SET active = false WHERE active"
                )
                connection.execute(
                    "UPDATE architecture_knowledge_releases "
                    "SET active = true WHERE release_id = %s",
                    (release.id,),
                )
                connection.execute(
                    "UPDATE architecture_knowledge_documents SET published = true "
                    "WHERE version_id = ANY(%s)",
                    ([item.id for item in release.documents],),
                )
                connection.execute(
                    "INSERT INTO architecture_knowledge_audit "
                    "(release_id, actor_id, action, revision, rationale) "
                    "VALUES (%s, %s, 'publish', %s, %s)",
                    (release.id, release.published_by, release.revision, rationale),
                )
        except psycopg.Error as exc:
            raise PersistenceError("Architecture publication failed.") from exc

    def delete_draft(self, release_id: str, expected_revision: int, actor_id: str) -> None:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    "SELECT 1 FROM architecture_knowledge_releases WHERE release_id = %s "
                    "AND revision = %s AND payload->>'status' = 'draft' AND NOT active FOR UPDATE",
                    (release_id, expected_revision),
                ).fetchone()
                if row is None:
                    raise KnowledgeConflictError("The draft changed; reload before discarding it.")
                connection.execute(
                    "DELETE FROM architecture_knowledge_chunks WHERE index_id IN "
                    "(SELECT index_id FROM architecture_knowledge_indexes WHERE release_id = %s)",
                    (release_id,),
                )
                for statement in (
                    "DELETE FROM architecture_knowledge_indexes WHERE release_id = %s",
                    "DELETE FROM architecture_catalogue_candidates WHERE release_id = %s",
                    "DELETE FROM architecture_extraction_runs WHERE release_id = %s",
                    "DELETE FROM architecture_knowledge_releases WHERE release_id = %s",
                ):
                    connection.execute(statement, (release_id,))
                connection.execute(
                    "INSERT INTO architecture_knowledge_audit "
                    "(release_id, actor_id, action, revision) VALUES (%s, %s, %s, %s)",
                    (release_id, actor_id, "discard_draft", expected_revision),
                )
        except psycopg.Error as exc:
            raise PersistenceError("Architecture knowledge write failed.") from exc
