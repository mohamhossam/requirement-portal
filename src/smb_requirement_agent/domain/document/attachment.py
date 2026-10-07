"""A file attached to a Requirement or draft, on its way to becoming a source document.

It is scanned and extracted in the background, then finalised into the
Requirement's documents. It never enters the shared reference library
(ADR-0099). Field names match the library's version record, which held
attachments before, so stored uploads keep reading back.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from smb_requirement_agent.domain.document.entities import (
    DocumentAsset,
    DocumentEvidenceBlock,
    DocumentExtractionWarning,
)
from smb_requirement_agent.domain.document.errors import InvalidDocumentError
from smb_requirement_agent.domain.document.ingestion import IngestionStage
from smb_requirement_agent.domain.shared.actors import ActorSnapshot
from smb_requirement_agent.domain.shared.staleness import require_aware


@dataclass(frozen=True)
class AttachmentTarget:
    source_id: str
    is_draft: bool
    include_in_analysis: bool
    document_id: str | None = None
    expected_version: int | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise InvalidDocumentError("Attachment source is required.")
        if (self.document_id is None) != (self.expected_version is None):
            raise InvalidDocumentError("Replacement requires the current document version.")


@dataclass(frozen=True)
class AttachmentFile:
    id: str
    filename: str
    mime_type: str
    size_bytes: int
    checksum: str
    uploaded_at: datetime
    uploaded_by: ActorSnapshot
    idempotency_key: str
    stage: IngestionStage = IngestionStage.QUEUED
    attempt: int = 0
    lease_token: str | None = None
    lease_until: datetime | None = None
    error: str | None = None
    extraction_version: str | None = None
    blocks: tuple[DocumentEvidenceBlock, ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_warnings: tuple[str, ...] = ()
    assets: tuple[DocumentAsset, ...] = ()
    warning_details: tuple[DocumentExtractionWarning, ...] = ()

    def __post_init__(self) -> None:
        require_aware(self.uploaded_at, "attachment upload time")
        if not self.id or self.size_bytes < 1 or not self.filename.strip():
            raise InvalidDocumentError("Attachment upload metadata is incomplete.")
        if len(self.checksum) != 64 or any(c not in "0123456789abcdef" for c in self.checksum):
            raise InvalidDocumentError("Attachment upload requires a SHA-256 checksum.")
        if self.stage is IngestionStage.READY and not self.blocks:
            raise InvalidDocumentError("Ready evidence must contain extracted blocks.")

    def _identity(self) -> tuple[object, ...]:
        return (
            self.id,
            self.checksum,
            self.filename,
            self.mime_type,
            self.size_bytes,
            self.uploaded_at,
            self.uploaded_by,
            self.idempotency_key,
        )


@dataclass(frozen=True)
class AttachmentUpload:
    id: str
    target: AttachmentTarget
    owner: ActorSnapshot
    file: AttachmentFile
    version: int = 1
    attached_document_id: str | None = None
    excluded: bool = False

    def __post_init__(self) -> None:
        if not self.id or self.version < 1:
            raise InvalidDocumentError("Attachment upload identity is required.")

    def update_file(self, value: AttachmentFile) -> AttachmentUpload:
        if value._identity() != self.file._identity():
            raise InvalidDocumentError("Original upload metadata is immutable.")
        return replace(self, file=value, version=self.version + 1)
