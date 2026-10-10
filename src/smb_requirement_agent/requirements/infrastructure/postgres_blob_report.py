"""How much the stored document files weigh, and how many nothing refers to (ADR-0079).

A blob is referenced by a source document version (removed documents included,
since their versions stay restorable) or by an attachment upload's file. The
report deletes nothing: an orphan is a lead for an operator, not a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession


@dataclass(frozen=True)
class DocumentBlobUsage:
    count: int
    size_bytes: int
    orphan_count: int
    orphan_size_bytes: int


class PostgresDocumentBlobReport:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def usage(self) -> DocumentBlobUsage:
        with self._store.connection() as connection:
            row = connection.execute(
                """
                WITH referenced AS (
                    SELECT version->>'id' AS id
                    FROM source_documents d
                    CROSS JOIN LATERAL jsonb_array_elements(d.payload->'versions') version
                    UNION
                    SELECT payload->'file'->>'id' FROM requirement_attachment_ingestions
                )
                SELECT count(*), coalesce(sum(b.size_bytes), 0),
                    count(*) FILTER (WHERE r.id IS NULL),
                    coalesce(sum(b.size_bytes) FILTER (WHERE r.id IS NULL), 0)
                FROM document_blobs b LEFT JOIN referenced r ON r.id=b.document_version_id
                """
            ).fetchone()
        if row is None:
            return DocumentBlobUsage(0, 0, 0, 0)
        return DocumentBlobUsage(*(int(str(value)) for value in row))
