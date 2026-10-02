"""In-memory source-document metadata and blob adapters."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from smb_requirement_agent.application.errors import (
    DocumentNotFoundError,
    DocumentStorageError,
    DocumentVersionConflictError,
)
from smb_requirement_agent.application.ports.document_repository import DocumentRepositoryPort
from smb_requirement_agent.application.ports.document_storage import DocumentStoragePort
from smb_requirement_agent.domain.document.entities import SourceDocument
from smb_requirement_agent.domain.document.value_objects import DocumentId, DocumentVersionId
from smb_requirement_agent.domain.requirement.value_objects import RequirementId


class InMemoryDocumentRepository(DocumentRepositoryPort):
    def __init__(self) -> None:
        self._documents: dict[str, SourceDocument] = {}

    def snapshot_state(self) -> Any:
        return deepcopy((self._documents,))

    def restore_state(self, state: Any) -> None:
        (self._documents,) = deepcopy(state)

    def add(self, document: SourceDocument) -> None:
        if document.id.value in self._documents:
            raise DocumentVersionConflictError("The document already exists.")
        self._documents[document.id.value] = document

    def get(self, document_id: DocumentId) -> SourceDocument | None:
        return self._documents.get(document_id.value)

    def save(self, document: SourceDocument) -> None:
        current = self._documents.get(document.id.value)
        if current is None:
            raise DocumentVersionConflictError("The document no longer exists. Reload it.")
        if current != document and document.version_number != current.version_number + 1:
            raise DocumentVersionConflictError(
                "The document changed before this mutation could be saved. Reload it."
            )
        self._documents[document.id.value] = document

    def list_all(self) -> list[SourceDocument]:
        return sorted(
            (item for item in self._documents.values() if not item.removed),
            key=lambda item: item.current_version.created_at,
            reverse=True,
        )

    def list_for_requirement(self, requirement_id: RequirementId) -> list[SourceDocument]:
        return [item for item in self.list_all() if item.requirement_id == requirement_id]

    def list_for_draft(self, draft_id: RequirementId) -> list[SourceDocument]:
        return [item for item in self.list_all() if item.draft_id == draft_id]


class InMemoryDocumentStorage(DocumentStoragePort):
    """Blobs, some written outside any unit of work, so the store takes the shared graph lock.

    An architecture upload stores its blob before its own save. Without the lock
    that write could land inside a transaction another thread owns, which would
    count it as its own write and roll the blob back.
    """

    def __init__(self, *, lock: RLock | None = None) -> None:
        self._blobs: dict[str, bytes] = {}
        self._lock = lock or RLock()

    def snapshot_state(self) -> Any:
        return deepcopy((self._blobs,))

    def restore_state(self, state: Any) -> None:
        (self._blobs,) = deepcopy(state)

    def put(self, version_id: DocumentVersionId, content: bytes) -> None:
        immutable = bytes(content)
        with self._lock:
            stored = self._blobs.get(version_id.value)
            if stored is not None and stored != immutable:
                raise DocumentStorageError(
                    f"Document content {version_id.value!r} is immutable and cannot be replaced."
                )
            self._blobs[version_id.value] = immutable

    def get(self, version_id: DocumentVersionId) -> bytes:
        with self._lock:
            content = self._blobs.get(version_id.value)
        if content is None:
            raise DocumentNotFoundError(f"Document content {version_id.value!r} was not found.")
        return content

    def delete(self, version_id: DocumentVersionId) -> None:
        with self._lock:
            self._blobs.pop(version_id.value, None)
