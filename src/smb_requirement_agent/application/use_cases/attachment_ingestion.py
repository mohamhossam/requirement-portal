"""Durable scanned attachment uploads, finalized atomically through UploadDocument.

Attachments are requirement work: they are scanned and extracted in the
background, then attached to their Requirement or draft. They never pass
through the shared reference library (ADR-0099).
"""

import hashlib
import uuid
from dataclasses import dataclass, replace
from datetime import timedelta

from smb_kernel.documents.ports import (
    DocumentExtractorPort,
    DocumentScannerPort,
    DocumentStoragePort,
    ExtractedDocument,
)
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    DocumentExtractionError,
    DocumentExtractionTimeoutError,
    DocumentNotFoundError,
    DocumentVersionConflictError,
    RequirementDraftNotFoundError,
    RequirementNotFoundError,
    UnsupportedDocumentError,
)
from smb_requirement_agent.application.ports.attachment_ingestions import (
    AttachmentIngestionRepositoryPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.documents import (
    UploadDocument,
    UploadDocumentInput,
    validate_ingested_upload,
)
from smb_requirement_agent.application.use_cases.identity_access import RequirementAccessService
from smb_requirement_agent.domain.document.attachment import (
    AttachmentFile,
    AttachmentTarget,
    AttachmentUpload,
)
from smb_requirement_agent.domain.document.errors import InvalidDocumentError
from smb_requirement_agent.domain.document.ingestion import (
    IN_PROGRESS_STAGES,
    STOPPED_STAGES,
    IngestionStage,
)
from smb_requirement_agent.domain.document.value_objects import (
    DocumentId,
    DocumentVersionId,
    ExtractionWarningSeverity,
)
from smb_requirement_agent.domain.identity.errors import AuthorizationDeniedError
from smb_requirement_agent.domain.shared.actors import ActorProfile
from smb_requirement_agent.domain.shared.identifiers import RequirementId

# A scan-and-extract attempt holds its lease this long: the background
# extraction deadline plus a minute of margin.
LEASE = timedelta(seconds=660)


@dataclass(frozen=True)
class AttachmentIngestionView:
    id: str
    version: int
    filename: str
    stage: IngestionStage
    error: str | None
    attached_document_id: str | None
    excluded: bool = False


class AttachmentIngestion:
    def __init__(
        self,
        repository: AttachmentIngestionRepositoryPort,
        storage: DocumentStoragePort,
        scanner: DocumentScannerPort,
        extractor: DocumentExtractorPort,
        upload: UploadDocument,
        access: RequirementAccessService,
        transactions: TransactionManagerPort,
        clock: ClockPort,
        max_file_bytes: int,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._scanner = scanner
        self._extractor = extractor
        self._upload = upload
        self._access = access
        self._transactions = transactions
        self._clock = clock
        self._max_file_bytes = max_file_bytes

    @property
    def max_file_bytes(self) -> int:
        return self._max_file_bytes

    def _authorize(self, target: AttachmentTarget, actor: ActorProfile) -> None:
        source_id = RequirementId(target.source_id)
        if target.is_draft:
            self._access.require_draft_owner(source_id, actor)
        else:
            self._access.require_requirement_member(source_id, actor)

    @staticmethod
    def _view(upload: AttachmentUpload) -> AttachmentIngestionView:
        return AttachmentIngestionView(
            upload.id,
            upload.version,
            upload.file.filename,
            upload.file.stage,
            upload.file.error,
            upload.attached_document_id,
            upload.excluded,
        )

    def list(
        self, source_id: str, is_draft: bool, actor: ActorProfile
    ) -> tuple[AttachmentIngestionView, ...]:
        self._authorize(AttachmentTarget(source_id, is_draft, False), actor)
        return tuple(self._view(u) for u in self._repository.list_for(source_id, is_draft))

    def submit(
        self, target: AttachmentTarget, data: UploadDocumentInput, key: str, actor: ActorProfile
    ) -> AttachmentIngestionView:
        with self._transactions.transaction():
            self._transactions.lock_requirement(RequirementId(target.source_id))
            self._authorize(target, actor)
            filename, mime = validate_ingested_upload(
                data.filename, data.mime_type, data.content, self._max_file_bytes
            )
            if not key.strip() or len(key) > 100:
                raise UnsupportedDocumentError(
                    "A title (up to 200 characters) and submission key (up to 100) are required."
                )
            digest = hashlib.sha256(data.content).hexdigest()
            existing = self._repository.find_submission(actor.id.value, key)
            if existing is not None:
                if (existing.file.checksum, existing.file.filename, existing.file.mime_type) != (
                    digest,
                    filename,
                    mime,
                ) or existing.target != target:
                    raise DocumentVersionConflictError(
                        "Submission key was used for different content."
                    )
                return self._view(existing)
            file = AttachmentFile(
                str(uuid.uuid4()),
                filename,
                mime,
                len(data.content),
                digest,
                self._clock.now(),
                actor.snapshot(),
                key,
            )
            self._storage.put(DocumentVersionId(file.id), data.content)
            upload = AttachmentUpload(str(uuid.uuid4()), target, actor.snapshot(), file)
            self._repository.add(upload)
            return self._view(upload)

    def control(
        self,
        source_id: str,
        is_draft: bool,
        ingestion_id: str,
        expected: int,
        retry: bool | None,
        actor: ActorProfile,
    ) -> AttachmentIngestionView:
        with self._transactions.transaction():
            self._authorize(AttachmentTarget(source_id, is_draft, False), actor)
            upload = self._repository.get(ingestion_id)
            if (
                upload is None
                or upload.target.source_id != source_id
                or upload.target.is_draft != is_draft
            ):
                raise DocumentNotFoundError("Attachment upload was not found.")
            if upload.version != expected:
                raise DocumentVersionConflictError("Processing changed. Reload its status.")
            file = upload.file
            if retry is None:
                if file.stage not in STOPPED_STAGES or upload.attached_document_id is not None:
                    raise DocumentVersionConflictError("Only stopped uploads can be excluded.")
                updated = replace(upload, excluded=True, version=upload.version + 1)
                self._repository.save(updated, upload.version)
                return self._view(updated)
            eligible = (
                {IngestionStage.FAILED, IngestionStage.CANCELLED} if retry else IN_PROGRESS_STAGES
            )
            if file.stage not in eligible or upload.attached_document_id is not None:
                raise DocumentVersionConflictError("Processing state does not allow this action.")
            updated = upload.update_file(
                replace(
                    file,
                    stage=IngestionStage.QUEUED if retry else IngestionStage.CANCELLED,
                    attempt=0 if retry else file.attempt,
                    lease_token=None,
                    lease_until=None,
                    error=None,
                )
            )
            updated = replace(updated, excluded=False)
            self._repository.save(updated, upload.version)
            return self._view(updated)

    def process_next(self) -> bool:
        """One unit of background work: scan one upload, then attach one extracted upload."""
        scanned = self.scan_next()
        attached = self.attach_next()
        return scanned or attached

    def scan_next(self) -> bool:
        token = str(uuid.uuid4())
        now = self._clock.now()
        upload = self._repository.claim(now, now + LEASE, token)
        if upload is None:
            return False
        file = upload.file
        if file.lease_token != token:
            return True  # An exhausted crashed attempt was made visible.
        try:
            content = self._storage.get(DocumentVersionId(file.id))
            if not self._scanner.scan(content):
                self._finish(
                    upload.id,
                    replace(
                        file,
                        stage=IngestionStage.QUARANTINED,
                        error="Malware scan rejected this upload. Publication is prohibited.",
                    ),
                    token,
                )
                return True
            file = replace(file, stage=IngestionStage.EXTRACTING)
            if not self._finish(upload.id, file, token, terminal=False):
                return True
            extraction = self._extractor.extract_structured(file.mime_type, content)
            if not extraction.evidence_blocks:
                raise DocumentExtractionError("Extraction produced no reviewable evidence.")
            ready = replace(
                file,
                stage=IngestionStage.READY,
                extraction_version=extraction.extraction_version,
                blocks=extraction.evidence_blocks,
                assets=extraction.assets,
                warning_details=extraction.warnings,
                warnings=tuple(w.message for w in extraction.warnings),
                blocking_warnings=tuple(
                    w.message
                    for w in extraction.warnings
                    if w.severity is ExtractionWarningSeverity.BLOCKING
                ),
            )
            self._finish(upload.id, ready, token)
        except (
            DocumentExtractionError,
            DocumentExtractionTimeoutError,
            UnsupportedDocumentError,
        ) as exc:
            self._finish(
                upload.id, replace(file, stage=IngestionStage.FAILED, error=str(exc)), token
            )
        return True

    def _finish(
        self, upload_id: str, file: AttachmentFile, token: str, *, terminal: bool = True
    ) -> bool:
        with self._transactions.transaction():
            current = self._repository.get(upload_id)
            if current is None:
                return False
            old = current.file
            if (
                old.lease_token != token
                or old.lease_until is None
                or old.lease_until <= self._clock.now()
            ):
                return False
            updated = current.update_file(
                replace(
                    file,
                    lease_token=None if terminal else token,
                    lease_until=None if terminal else old.lease_until,
                )
            )
            self._repository.save(updated, current.version)
            return True

    def attach_next(self) -> bool:
        pending = self._repository.pending_finalization()
        if pending is None:
            return False
        target = pending.target
        with self._transactions.transaction():
            self._transactions.lock_requirement(RequirementId(target.source_id))
            upload = self._repository.get(pending.id)
            if upload is None or upload.version != pending.version:
                return True
            file = upload.file
            actor = ActorProfile(upload.owner.id, upload.owner.display_name, upload.owner.email)
            try:
                self._authorize(target, actor)
                extraction = ExtractedDocument(
                    "\n\n".join(b.text for b in file.blocks if b.text),
                    file.extraction_version or "unknown",
                    file.blocks,
                    file.warning_details,
                    file.assets,
                )
                attached = self._upload.accept_extraction(
                    UploadDocumentInput(
                        file.filename,
                        file.mime_type,
                        self._storage.get(DocumentVersionId(file.id)),
                        target.include_in_analysis,
                    ),
                    actor,
                    None if target.is_draft else RequirementId(target.source_id),
                    RequirementId(target.source_id) if target.is_draft else None,
                    DocumentId(target.document_id) if target.document_id else None,
                    target.expected_version,
                    extraction,
                )
            except (
                AuthorizationDeniedError,
                DocumentVersionConflictError,
                DocumentNotFoundError,
                RequirementDraftNotFoundError,
                RequirementNotFoundError,
                InvalidDocumentError,
            ):
                updated = upload.update_file(
                    replace(
                        file,
                        stage=IngestionStage.FAILED,
                        error="Attachment source or access changed. "
                        "Reload the source before retrying.",
                    )
                )
            else:
                updated = replace(
                    upload, attached_document_id=attached.id.value, version=upload.version + 1
                )
            self._repository.save(updated, upload.version)
        return True
