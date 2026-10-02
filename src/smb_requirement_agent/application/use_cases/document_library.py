"""Standalone uploads and content-bound review, independent of Requirement records."""

from __future__ import annotations

import base64
import hashlib
import re
import uuid
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import PurePosixPath, PureWindowsPath

from smb_kernel.documents.ports import DocumentExtractorPort, DocumentStoragePort
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    DocumentExtractionError,
    DocumentExtractionTimeoutError,
    DocumentNotFoundError,
    DocumentVersionConflictError,
    UnsupportedDocumentError,
)
from smb_requirement_agent.application.ports.document_library import (
    DocumentLibraryPort,
    DocumentScannerPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.documents import (
    SUPPORTED_EXTENSIONS,
    UploadDocumentInput,
)
from smb_requirement_agent.domain.document.library import (
    AttachmentTarget,
    ExtractionRevision,
    IngestionStage,
    LibraryDocument,
    LibraryVersion,
    Publication,
    ReviewedPassage,
    require_submittable_passages,
)
from smb_requirement_agent.domain.document.value_objects import (
    DocumentVersionId,
    ExtractionWarningSeverity,
)
from smb_requirement_agent.domain.identity.entities import ActorProfile, ActorSnapshot
from smb_requirement_agent.domain.identity.errors import AuthorizationDeniedError

CHUNKING_POLICY = "structure-512-768-v1"
TABLE_CHUNKING_POLICY = "table-fields-512-768-v2"


@dataclass(frozen=True)
class LibraryView:
    id: str
    title: str
    owner: ActorSnapshot
    versions: tuple[LibraryVersion, ...]
    version: int
    publications: tuple[Publication, ...]
    published_id: str | None
    can_edit: bool
    review_fingerprint: str | None
    build_fingerprint: str | None = None


@dataclass(frozen=True)
class OriginalPreview:
    location: str
    image_data: str | None
    explanation: str


class DocumentLibrary:
    def __init__(
        self,
        repository: DocumentLibraryPort,
        storage: DocumentStoragePort,
        extractor: DocumentExtractorPort,
        scanner: DocumentScannerPort,
        transactions: TransactionManagerPort,
        clock: ClockPort,
        max_file_bytes: int,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._extractor = extractor
        self._scanner = scanner
        self._transactions = transactions
        self._clock = clock
        self.max_file_bytes = max_file_bytes

    def _get(self, document_id: str) -> LibraryDocument:
        value = self._repository.get(document_id)
        if value is None:
            raise DocumentNotFoundError("Library document was not found.")
        return value

    def _owned(self, document_id: str, actor: ActorProfile, expected: int) -> LibraryDocument:
        document = self._get(document_id)
        if document.attachment_target is not None:
            raise DocumentNotFoundError("Use the Requirement attachment processing controls.")
        if document.owner.id != actor.id:
            raise AuthorizationDeniedError("Only the document owner can change this document.")
        if document.version != expected:
            raise DocumentVersionConflictError("Document changed. Reload before retrying.")
        return document

    @staticmethod
    def _visible(document: LibraryDocument, actor: ActorProfile) -> LibraryView:
        if document.attachment_target is not None:
            raise DocumentNotFoundError("Requirement upload is not a shared library document.")
        if document.owner.id == actor.id:
            latest = document.versions[-1]
            return LibraryView(
                document.id,
                document.title,
                document.owner,
                tuple(
                    replace(v, blocking_warnings=v.unresolved_blocking_warnings)
                    for v in document.versions
                ),
                document.version,
                document.publications,
                document.published_id,
                True,
                latest.revisions[-1].fingerprint(latest.id, CHUNKING_POLICY)
                if latest.revisions
                else None,
                latest.revisions[-1].fingerprint(latest.id, TABLE_CHUNKING_POLICY)
                if latest.revisions
                else None,
            )
        publication = next(
            (
                p
                for p in document.publications
                if p.id == document.published_id and p.withdrawn_at is None
            ),
            None,
        )
        if publication is None:
            raise DocumentNotFoundError("Published library document was not found.")
        source = document.file_version(publication.version_id)
        revision = next(r for r in source.revisions if r.id == publication.revision_id)
        selected = {p.block_id: p for p in revision.passages if p.included}
        # A public response must not include unselected text, pending versions or prior extractions.
        safe_source = replace(
            source,
            idempotency_key="",
            warnings=(),
            warning_details=(),
            blocking_warnings=(),
            assets=(),
            blocks=tuple(
                replace(b, text=selected[b.id].text) for b in source.blocks if b.id in selected
            ),
            revisions=(replace(revision, passages=tuple(selected.values())),),
        )
        return LibraryView(
            document.id,
            document.title,
            document.owner,
            (safe_source,),
            document.version,
            (publication,),
            document.published_id,
            False,
            None,
        )

    def get(self, document_id: str, actor: ActorProfile) -> LibraryView:
        return self._visible(self._get(document_id), actor)

    def list(
        self, actor: ActorProfile, offset: int = 0, limit: int = 50
    ) -> tuple[LibraryView, ...]:
        return tuple(
            self._visible(d, actor)
            for d in self._repository.list_visible(actor.id.value, offset, limit)
        )

    def submit(
        self,
        title: str,
        data: UploadDocumentInput,
        key: str,
        actor: ActorProfile,
        document_id: str | None = None,
        expected: int | None = None,
        attachment_target: AttachmentTarget | None = None,
    ) -> LibraryDocument:
        filename = data.filename.strip()
        mime = data.mime_type.split(";", 1)[0].strip().lower()
        extension = PurePosixPath(filename).suffix.lower()
        if mime in {"", "application/octet-stream"}:
            mime = next(
                (
                    m
                    for m, suffixes in SUPPORTED_EXTENSIONS.items()
                    if extension in ((suffixes,) if isinstance(suffixes, str) else suffixes)
                ),
                mime,
            )
        suffixes = SUPPORTED_EXTENSIONS.get(mime)
        if (
            not filename
            or "\x00" in filename
            or len(filename) > 255
            or PurePosixPath(filename).name != filename
            or PureWindowsPath(filename).name != filename
            or not suffixes
            or not filename.lower().endswith(suffixes)
            or not 0 < len(data.content) <= self.max_file_bytes
        ):
            raise UnsupportedDocumentError(
                "Provide a supported, nonempty file within the upload limit, "
                "without a path in its name."
            )
        if not title.strip() or len(title) > 200 or not key.strip() or len(key) > 100:
            raise UnsupportedDocumentError(
                "A title (up to 200 characters) and submission key (up to 100) are required."
            )
        digest = hashlib.sha256(data.content).hexdigest()
        with self._transactions.transaction():
            existing = self._repository.find_submission(actor.id.value, key)
            if existing is not None:
                if existing.owner.id != actor.id:
                    raise AuthorizationDeniedError("This upload now belongs to another owner.")
                original = next(
                    v
                    for v in existing.versions
                    if v.idempotency_key == key and v.uploaded_by.id == actor.id
                )
                if (
                    (original.checksum, original.filename, original.mime_type)
                    != (
                        digest,
                        filename,
                        mime,
                    )
                    or existing.title != title.strip()
                    or existing.attachment_target != attachment_target
                    or (document_id is not None and existing.id != document_id)
                ):
                    raise DocumentVersionConflictError(
                        "Submission key was used for different content."
                    )
                return existing
            document = self._owned(document_id, actor, expected or 0) if document_id else None
            version = LibraryVersion(
                str(uuid.uuid4()),
                len(document.versions) + 1 if document else 1,
                filename,
                mime,
                len(data.content),
                digest,
                self._clock.now(),
                actor.snapshot(),
                key,
            )
            self._storage.put(DocumentVersionId(version.id), data.content)
            if document is None:
                document = LibraryDocument(
                    str(uuid.uuid4()),
                    title.strip(),
                    actor.snapshot(),
                    (version,),
                    attachment_target=attachment_target,
                )
                self._repository.add(document)
            else:
                updated = replace(
                    document, versions=(*document.versions, version), version=document.version + 1
                )
                self._repository.save(updated, document.version)
                document = updated
            return document

    def original(
        self, document_id: str, version_id: str, actor: ActorProfile
    ) -> tuple[LibraryVersion, bytes]:
        document = self._get(document_id)
        if document.attachment_target is not None:
            raise DocumentNotFoundError("Use the Requirement attachment review.")
        if document.owner.id != actor.id:
            raise AuthorizationDeniedError(
                "Original files may contain excluded material; only the owner can download them."
            )
        version = document.file_version(version_id)
        return version, self._storage.get(DocumentVersionId(version.id))

    def preview_original(
        self, document_id: str, version_id: str, block_id: str, actor: ActorProfile
    ) -> OriginalPreview:
        source, content = self.original(document_id, version_id, actor)
        if source.stage is not IngestionStage.READY:
            raise DocumentVersionConflictError(
                "Finish safe extraction before previewing the source."
            )
        block = next((b for b in source.blocks if b.id == block_id), None)
        if block is None:
            raise DocumentNotFoundError("Source passage was not found in this file version.")
        asset = next((a for a in source.assets if a.block_id == block_id), None)
        page = re.match(r"Page (\d+)(?:\D|$)", block.label)
        slide = re.match(r"Slide (\d+)(?:\D|$)", block.label)
        if asset:
            path, mime = asset.package_path, asset.mime_type
        elif source.mime_type == "application/pdf" and page:
            path, mime = f"pdf-page/{page[1]}", "image/jpeg"
        elif source.mime_type in {"image/png", "image/jpeg"}:
            path, mime = "image", source.mime_type
        elif source.mime_type.endswith("presentationml.presentation") and slide:
            path, mime = f"office-slide/{slide[1]}", "image/jpeg"
        else:
            return OriginalPreview(
                block.label,
                None,
                "A safe visual preview is unavailable for this source region. "
                "Download the original to compare its layout; "
                "extracted text is not a visual preview.",
            )
        try:
            raw = self._extractor.extract_asset(source.mime_type, content, path)
        except UnsupportedDocumentError as exc:
            return OriginalPreview(block.label, None, str(exc))
        if asset and hashlib.sha256(raw).hexdigest() != asset.checksum_sha256:
            raise DocumentExtractionError("Source preview no longer matches the extracted asset.")
        if raw.startswith(b"\xff\xd8"):
            mime = "image/jpeg"
        elif raw.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        else:
            raise DocumentExtractionError("Source preview is not a safe raster image.")
        return OriginalPreview(
            block.label,
            f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}",
            "Original source rendered as a safe raster. Page previews may include excluded content "
            "and are visible only to the owner. "
            "Region coordinates are shown in the passage location.",
        )

    def review(
        self,
        document_id: str,
        version_id: str,
        expected: int,
        actor: ActorProfile,
        passages: tuple[ReviewedPassage, ...],
        explanation: str,
    ) -> LibraryDocument:
        require_submittable_passages(passages)
        with self._transactions.transaction():
            document = self._owned(document_id, actor, expected)
            if sum(len(p.text) for p in passages) > 2_000_000:
                raise UnsupportedDocumentError(
                    "Reviewed text exceeds the two-million-character limit."
                )
            updated = document.review(
                version_id,
                ExtractionRevision(
                    str(uuid.uuid4()), self._clock.now(), actor.snapshot(), passages, explanation
                ),
            )
            self._repository.save(updated, expected)
            return updated

    def approve(
        self,
        document_id: str,
        version_id: str,
        revision_id: str,
        fingerprint: str,
        expected: int,
        actor: ActorProfile,
    ) -> LibraryDocument:
        with self._transactions.transaction():
            document = self._owned(document_id, actor, expected)
            if any(
                p.requires_activation and p.activated_at is None and p.withdrawn_at is None
                for p in document.publications
            ):
                raise DocumentVersionConflictError("Activate or discard the pending build first.")
            updated = document.approve(
                Publication(
                    str(uuid.uuid4()),
                    version_id,
                    revision_id,
                    fingerprint,
                    CHUNKING_POLICY,
                    actor.snapshot(),
                    self._clock.now(),
                )
            )
            self._repository.save(updated, expected)
            return updated

    def withdraw(
        self, document_id: str, expected: int, actor: ActorProfile, reason: str
    ) -> LibraryDocument:
        with self._transactions.transaction():
            document = self._owned(document_id, actor, expected)
            updated = document.withdraw(self._clock.now(), reason)
            self._repository.save(updated, expected)
            return updated

    def retry_index(self, document_id: str, expected: int, actor: ActorProfile) -> LibraryDocument:
        with self._transactions.transaction():
            document = self._owned(document_id, actor, expected)
            if not document.publications or document.publications[-1].withdrawn_at is not None:
                raise DocumentVersionConflictError("No eligible publication exists to retry.")
            publication = document.publications[-1]
            if (
                publication.activated_at is not None
                or publication.built_at is not None
                or publication.indexing_attempts < 3
            ):
                raise DocumentVersionConflictError("Indexing has not reached a terminal failure.")
            updated = replace(
                document,
                version=document.version + 1,
                publications=(
                    *document.publications[:-1],
                    replace(
                        publication,
                        indexing_attempts=0,
                        indexing_error=None,
                        index_lease_until=None,
                    ),
                ),
            )
            self._repository.save(updated, expected)
            return updated

    def control(
        self, document_id: str, version_id: str, expected: int, actor: ActorProfile, retry: bool
    ) -> LibraryDocument:
        with self._transactions.transaction():
            document = self._owned(document_id, actor, expected)
            version = document.file_version(version_id)
            eligible = (
                {IngestionStage.FAILED, IngestionStage.CANCELLED}
                if retry
                else {IngestionStage.QUEUED, IngestionStage.SCANNING, IngestionStage.EXTRACTING}
            )
            if version.stage not in eligible:
                raise DocumentVersionConflictError(
                    "This processing state does not allow that action."
                )
            updated = document.update_file(
                replace(
                    version,
                    stage=IngestionStage.QUEUED if retry else IngestionStage.CANCELLED,
                    attempt=0 if retry else version.attempt,
                    lease_token=None,
                    lease_until=None,
                    error=None,
                )
            )
            self._repository.save(updated, expected)
            return updated

    def process_next(self) -> bool:
        token = str(uuid.uuid4())
        now = self._clock.now()
        document = self._repository.claim(now, now + timedelta(seconds=660), token)
        if document is None:
            return False
        source = next((v for v in document.versions if v.lease_token == token), None)
        if source is None:
            return True  # Exhausted crashed attempt was made visible.
        try:
            content = self._storage.get(DocumentVersionId(source.id))
            if not self._scanner.scan(content):
                self._finish(
                    document.id,
                    replace(
                        source,
                        stage=IngestionStage.QUARANTINED,
                        error="Malware scan rejected this upload. Publication is prohibited.",
                    ),
                    token,
                )
                return True
            source = replace(source, stage=IngestionStage.EXTRACTING)
            if not self._finish(document.id, source, token, terminal=False):
                return True
            extraction = self._extractor.extract_structured(source.mime_type, content)
            if not extraction.evidence_blocks:
                raise DocumentExtractionError("Extraction produced no reviewable evidence.")
            ready = replace(
                source,
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
            self._finish(document.id, ready, token)
        except (
            DocumentExtractionError,
            DocumentExtractionTimeoutError,
            UnsupportedDocumentError,
        ) as exc:
            self._finish(
                document.id, replace(source, stage=IngestionStage.FAILED, error=str(exc)), token
            )
        return True

    def _finish(
        self, document_id: str, source: LibraryVersion, token: str, *, terminal: bool = True
    ) -> bool:
        with self._transactions.transaction():
            current = self._get(document_id)
            old = current.file_version(source.id)
            if (
                old.lease_token != token
                or old.lease_until is None
                or old.lease_until <= self._clock.now()
            ):
                return False
            updated = current.update_file(
                replace(
                    source,
                    lease_token=None if terminal else token,
                    lease_until=None if terminal else old.lease_until,
                )
            )
            self._repository.save(updated, current.version)
            return True
