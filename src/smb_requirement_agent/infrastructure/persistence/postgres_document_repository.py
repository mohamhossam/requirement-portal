"""PostgreSQL metadata and immutable-byte adapters for source documents."""

import hashlib

from smb_requirement_agent.application.errors import DocumentNotFoundError, DocumentStorageError
from smb_requirement_agent.application.ports.document_storage import DocumentStoragePort
from smb_requirement_agent.domain.document.value_objects import DocumentVersionId
from smb_requirement_agent.infrastructure.persistence.postgres_document_metadata import (
    PostgresDocumentRepository as PostgresDocumentRepository,
)
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import _integer


class PostgresDocumentStorage(DocumentStoragePort):
    """Store immutable document bytes in the caller's PostgreSQL unit of work."""

    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def put(self, version_id: DocumentVersionId, content: bytes) -> None:
        checksum = hashlib.sha256(content).hexdigest()
        with self._store.connection() as connection:
            connection.execute(
                """
                INSERT INTO document_blobs
                    (document_version_id, checksum_sha256, size_bytes, content)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (document_version_id) DO NOTHING
                """,
                (version_id.value, checksum, len(content), content),
            )
            row = connection.execute(
                """
                SELECT checksum_sha256, size_bytes, content FROM document_blobs
                WHERE document_version_id=%s
                """,
                (version_id.value,),
            ).fetchone()
            stored_content = _stored_bytes(row[2]) if row is not None else b""
            if (
                row is None
                or str(row[0]) != checksum
                or _integer(row[1]) != len(content)
                or hashlib.sha256(stored_content).hexdigest() != checksum
            ):
                raise DocumentStorageError(
                    "Document version ID already refers to different immutable bytes."
                )

    def get(self, version_id: DocumentVersionId) -> bytes:
        with self._store.connection() as connection:
            row = connection.execute(
                """
                SELECT content, checksum_sha256, size_bytes FROM document_blobs
                WHERE document_version_id=%s
                """,
                (version_id.value,),
            ).fetchone()
        if row is None:
            raise DocumentNotFoundError(f"Document content {version_id.value!r} was not found.")
        content = _stored_bytes(row[0])
        if len(content) != _integer(row[2]) or hashlib.sha256(content).hexdigest() != str(row[1]):
            raise DocumentStorageError("Stored document bytes failed their integrity check.")
        return content

    def delete(self, version_id: DocumentVersionId) -> None:
        """Remove a blob only when its surrounding application action is rolling back."""
        with self._store.connection() as connection:
            connection.execute(
                "DELETE FROM document_blobs WHERE document_version_id=%s",
                (version_id.value,),
            )


def _stored_bytes(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    raise DocumentStorageError("Stored document content is not binary data.")
