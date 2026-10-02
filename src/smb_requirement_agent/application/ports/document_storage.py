"""Blob-storage boundary for immutable document bytes."""

from typing import Protocol

from smb_requirement_agent.domain.document.value_objects import DocumentVersionId


class DocumentStoragePort(Protocol):
    def put(self, version_id: DocumentVersionId, content: bytes) -> None: ...
    def get(self, version_id: DocumentVersionId) -> bytes: ...
    def delete(self, version_id: DocumentVersionId) -> None: ...
