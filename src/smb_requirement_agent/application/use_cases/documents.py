"""Source-document upload, review, inclusion, removal, and context assembly."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, replace
from pathlib import PurePosixPath, PureWindowsPath

from smb_kernel.documents.ports import (
    DocumentExtractorPort,
    DocumentStoragePort,
    ExtractedDocument,
)
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    DocumentContextTooLargeError,
    DocumentExtractionError,
    DocumentNotFoundError,
    DocumentVersionConflictError,
    UnsupportedDocumentError,
)
from smb_requirement_agent.application.ports.document_repository import DocumentRepositoryPort
from smb_requirement_agent.application.ports.requirement_analyzer import AnalysisDocumentContext
from smb_requirement_agent.application.ports.requirement_draft_repository import (
    RequirementDraftRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_repository import RequirementRepositoryPort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementAccessService,
    RequirementPermission,
)
from smb_requirement_agent.application.use_cases.invalidate_derived_artifacts import (
    InvalidateDerivedArtifacts,
)
from smb_requirement_agent.application.use_cases.requirement_sources import source_eligibility
from smb_requirement_agent.domain.analysis.entities import AnalysisDocumentReference
from smb_requirement_agent.domain.document.entities import SourceDocument, SourceDocumentVersion
from smb_requirement_agent.domain.document.value_objects import (
    AnalysisReadiness,
    DocumentId,
    DocumentVersionId,
    ExtractionStatus,
)
from smb_requirement_agent.domain.requirement.entities import (
    AnalysisEligibility,
    Requirement,
    RequirementDraft,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

SUPPORTED_EXTENSIONS: dict[str, str | tuple[str, ...]] = {
    "text/csv": ".csv",
    "text/tab-separated-values": ".tsv",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "text/plain": (".txt", ".md"),
    "text/markdown": (".md",),
    "image/png": (".png",),
    "image/jpeg": (".jpg", ".jpeg"),
}


def validate_ingested_upload(
    filename: str, mime_type: str, content: bytes, max_bytes: int
) -> tuple[str, str]:
    """The checks for a file scanned and extracted in the background.

    The declared type wins; an absent or generic one is inferred from the
    extension. Returns the cleaned filename and the type it will be read as.
    """
    filename = filename.strip()
    mime = mime_type.split(";", 1)[0].strip().lower()
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
        or not 0 < len(content) <= max_bytes
    ):
        raise UnsupportedDocumentError(
            "Provide a supported, nonempty file within the upload limit, "
            "without a path in its name."
        )
    return filename, mime


@dataclass(frozen=True)
class UploadDocumentInput:
    filename: str
    mime_type: str
    content: bytes
    include_in_analysis: bool = False


@dataclass(frozen=True)
class AnalysisDocumentSelection:
    contexts: tuple[AnalysisDocumentContext, ...]
    references: tuple[AnalysisDocumentReference, ...]


class UploadDocument:
    def __init__(
        self,
        documents: DocumentRepositoryPort,
        storage: DocumentStoragePort,
        extractor: DocumentExtractorPort,
        requirements: RequirementRepositoryPort,
        drafts: RequirementDraftRepositoryPort,
        invalidation: InvalidateDerivedArtifacts,
        transactions: TransactionManagerPort,
        access: RequirementAccessService,
        clock: ClockPort,
        max_file_bytes: int,
    ) -> None:
        self._documents = documents
        self._storage = storage
        self._extractor = extractor
        self._requirements = requirements
        self._drafts = drafts
        self._invalidation = invalidation
        self._transactions = transactions
        self._access = access
        self._clock = clock
        self._max_file_bytes = max_file_bytes

    @property
    def max_file_bytes(self) -> int:
        return self._max_file_bytes

    def for_requirement(
        self,
        requirement_id: RequirementId,
        data: UploadDocumentInput,
        actor: ActorProfile,
        document_id: DocumentId | None = None,
        *,
        expected_version: int | None = None,
    ) -> SourceDocument:
        self._access.require_requirement_member(requirement_id, actor)
        return self._upload(data, actor, requirement_id, None, document_id, expected_version, None)

    def for_draft(
        self,
        draft_id: RequirementId,
        data: UploadDocumentInput,
        actor: ActorProfile,
        document_id: DocumentId | None = None,
        *,
        expected_version: int | None = None,
    ) -> SourceDocument:
        self._access.require_draft_owner(draft_id, actor)
        return self._upload(data, actor, None, draft_id, document_id, expected_version, None)

    def accept_extraction(
        self,
        data: UploadDocumentInput,
        actor: ActorProfile,
        requirement_id: RequirementId | None,
        draft_id: RequirementId | None,
        document_id: DocumentId | None,
        expected_version: int | None,
        extraction: ExtractedDocument,
    ) -> SourceDocument:
        """Commit a scanned worker result through the existing attachment invariants."""
        return self._upload(
            data, actor, requirement_id, draft_id, document_id, expected_version, extraction
        )

    def _upload(
        self,
        data: UploadDocumentInput,
        actor: ActorProfile,
        requirement_id: RequirementId | None,
        draft_id: RequirementId | None,
        document_id: DocumentId | None,
        expected_version: int | None,
        prepared: ExtractedDocument | None,
    ) -> SourceDocument:
        filename, mime_type = self._validate(data)
        preflight = self._documents.get(document_id) if document_id is not None else None
        if document_id is not None and preflight is None:
            raise DocumentNotFoundError(f"Document {document_id.value!r} not found.")
        if preflight is not None and (
            preflight.requirement_id != requirement_id or preflight.draft_id != draft_id
        ):
            raise DocumentNotFoundError("Document does not belong to this source record.")
        if preflight is not None and preflight.version_number != expected_version:
            raise DocumentVersionConflictError("The document changed. Reload it before uploading.")
        version_id = DocumentVersionId(str(uuid.uuid4()))
        checksum = hashlib.sha256(data.content).hexdigest()
        try:
            extraction = (
                prepared
                if prepared is not None
                else self._extractor.extract_structured(mime_type, data.content)
            )
            extracted_text = extraction.text
            status = ExtractionStatus.READY
            extraction_error = None
        except DocumentExtractionError as exc:
            extraction = None
            extracted_text = None
            status = ExtractionStatus.FAILED
            extraction_error = str(exc)

        version = SourceDocumentVersion(
            id=version_id,
            number=1,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data.content),
            checksum_sha256=checksum,
            extraction_status=status,
            created_at=self._clock.now(),
            extracted_text=extracted_text,
            extraction_error=extraction_error,
            extraction_version=extraction.extraction_version if extraction else None,
            evidence_blocks=extraction.evidence_blocks if extraction else (),
            extraction_warnings=extraction.warnings if extraction else (),
            assets=extraction.assets if extraction else (),
        )
        with self._transactions.transaction():
            source_id = requirement_id or draft_id
            if source_id is None:
                raise AssertionError("A document upload requires a Requirement or draft identity.")
            self._transactions.lock_requirement(source_id)
            if requirement_id is not None:
                self._access.require_requirement_member(requirement_id, actor)
            else:
                self._access.require_draft_owner(source_id, actor)
            existing = self._documents.get(document_id) if document_id is not None else None
            if document_id is not None and existing is None:
                raise DocumentNotFoundError(f"Document {document_id.value!r} not found.")
            if existing is not None and (
                existing.requirement_id != requirement_id or existing.draft_id != draft_id
            ):
                raise DocumentNotFoundError("Document does not belong to this source record.")
            if existing is not None and existing.version_number != expected_version:
                raise DocumentVersionConflictError(
                    "The document changed while extraction was in progress. Reload it."
                )
            if existing is None:
                document = SourceDocument(
                    id=document_id or DocumentId(str(uuid.uuid4())),
                    versions=(version,),
                    requirement_id=requirement_id,
                    draft_id=draft_id,
                    requires_attention=data.include_in_analysis
                    and version.analysis_readiness is AnalysisReadiness.BLOCKED,
                )
                if (
                    data.include_in_analysis
                    and version.analysis_readiness is not AnalysisReadiness.BLOCKED
                ):
                    document = document.set_included(True)
                self._storage.put(version_id, data.content)
                self._documents.add(document)
                if document.is_included and requirement_id is not None:
                    self._invalidation.for_changed_requirement(requirement_id)
                return document

            was_included = existing.is_included
            version = SourceDocumentVersion(
                id=version.id,
                number=len(existing.versions) + 1,
                filename=version.filename,
                mime_type=version.mime_type,
                size_bytes=version.size_bytes,
                checksum_sha256=version.checksum_sha256,
                extraction_status=version.extraction_status,
                created_at=version.created_at,
                extracted_text=version.extracted_text,
                extraction_error=version.extraction_error,
                extraction_version=version.extraction_version,
                evidence_blocks=version.evidence_blocks,
                extraction_warnings=version.extraction_warnings,
                assets=version.assets,
            )
            document = existing.add_version(version)
            if (
                data.include_in_analysis
                and version.analysis_readiness is not AnalysisReadiness.BLOCKED
            ):
                document = document.set_included(True)
            document = replace(
                document,
                version_number=existing.version_number + 1,
                requires_attention=(data.include_in_analysis or existing.requires_attention)
                and version.analysis_readiness is AnalysisReadiness.BLOCKED,
            )
            self._storage.put(version_id, data.content)
            self._documents.save(document)
            if (was_included or document.is_included) and requirement_id is not None:
                self._invalidation.for_changed_requirement(requirement_id)
            return document

    def _validate(self, data: UploadDocumentInput) -> tuple[str, str]:
        filename = data.filename.strip()
        if (
            not filename
            or "\x00" in filename
            or PurePosixPath(filename).name != filename
            or PureWindowsPath(filename).name != filename
        ):
            raise UnsupportedDocumentError("Document filename must not contain a path.")
        if not data.content:
            raise UnsupportedDocumentError("Document file must not be empty.")
        if len(data.content) > self._max_file_bytes:
            raise UnsupportedDocumentError(
                f"Document exceeds the {self._max_file_bytes} byte upload limit."
            )
        mime_type = data.mime_type.split(";", 1)[0].strip().lower()
        suffix = PurePosixPath(filename.lower()).suffix
        # Browsers frequently supply an empty/octet-stream MIME for Markdown.
        if suffix == ".md" and mime_type in {
            "",
            "application/octet-stream",
            "text/plain",
            "text/x-markdown",
        }:
            mime_type = "text/markdown"
        expected_extension = SUPPORTED_EXTENSIONS.get(mime_type)
        if expected_extension is None or not filename.lower().endswith(expected_extension):
            raise UnsupportedDocumentError(
                "Document extension and declared MIME type must agree "
                "for PDF, DOCX, XLSX, TXT, MD, PNG, or JPEG."
            )
        return filename, mime_type


class ListDocuments:
    def __init__(self, documents: DocumentRepositoryPort, access: RequirementAccessService) -> None:
        self._documents = documents
        self._access = access

    def visible_to(self, actor: ActorProfile) -> tuple[SourceDocument, ...]:
        """Requirement documents, plus attachments of drafts the actor may open."""
        return tuple(
            item
            for item in self._documents.list_all()
            if item.draft_id is None or self._access.can_access_draft(item.draft_id, actor)
        )

    def for_owned_draft(
        self, draft_id: RequirementId, actor: ActorProfile
    ) -> tuple[SourceDocument, ...]:
        self._access.require_draft_owner(draft_id, actor)
        return self.for_draft(draft_id)

    def for_requirement(self, requirement_id: RequirementId) -> tuple[SourceDocument, ...]:
        return tuple(self._documents.list_for_requirement(requirement_id))

    def for_draft(self, draft_id: RequirementId) -> tuple[SourceDocument, ...]:
        return tuple(self._documents.list_for_draft(draft_id))

    def eligibility(self, source: Requirement | RequirementDraft) -> AnalysisEligibility:
        documents = (
            self.for_draft(source.id)
            if isinstance(source, RequirementDraft)
            else self.for_requirement(source.id)
        )
        return source_eligibility(source, documents)


class GetDocument:
    """Read a document the actor may open: draft attachments are owner-only."""

    def __init__(
        self,
        documents: DocumentRepositoryPort,
        storage: DocumentStoragePort,
        extractor: DocumentExtractorPort,
        access: RequirementAccessService,
    ) -> None:
        self._documents = documents
        self._storage = storage
        self._extractor = extractor
        self._access = access

    def execute(self, document_id: DocumentId, actor: ActorProfile) -> SourceDocument:
        document = self._documents.get(document_id)
        if document is None or document.removed:
            raise DocumentNotFoundError(f"Document {document_id.value!r} not found.")
        if document.draft_id is not None:
            self._access.require_draft_owner(document.draft_id, actor)
        return document

    def blob(
        self, document_id: DocumentId, version_id: DocumentVersionId | None, actor: ActorProfile
    ) -> bytes:
        document = self.execute(document_id, actor)
        version = document.current_version if version_id is None else document.version(version_id)
        return self._storage.get(version.id)

    def asset(
        self,
        document_id: DocumentId,
        version_id: DocumentVersionId,
        asset_id: str,
        actor: ActorProfile,
    ) -> tuple[str, bytes]:
        document = self.execute(document_id, actor)
        version = document.version(version_id)
        asset = next((item for item in version.assets if item.id == asset_id.strip()), None)
        if asset is None:
            raise DocumentNotFoundError("Document image asset was not found.")
        content = self._storage.get(version.id)
        extracted = self._extractor.extract_asset(version.mime_type, content, asset.package_path)
        if hashlib.sha256(extracted).hexdigest() != asset.checksum_sha256:
            raise DocumentExtractionError("Document image asset checksum changed unexpectedly.")
        return asset.mime_type, extracted


class SetDocumentInclusion:
    def __init__(
        self,
        documents: DocumentRepositoryPort,
        invalidation: InvalidateDerivedArtifacts,
        transactions: TransactionManagerPort,
        *,
        authorization: RequirementAccessService,
    ) -> None:
        self._authorization = authorization
        self._documents = documents
        self._invalidation = invalidation
        self._transactions = transactions

    def execute(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        document_id: DocumentId,
        included: bool,
        expected_version: int,
    ) -> SourceDocument:
        return self._authorization.execute_mutation(
            requirement_id,
            actor,
            RequirementPermission.MEMBER,
            lambda: self._execute(
                requirement_id=requirement_id,
                document_id=document_id,
                included=included,
                expected_version=expected_version,
            ),
        )

    def _execute(
        self,
        requirement_id: RequirementId,
        document_id: DocumentId,
        included: bool,
        expected_version: int,
    ) -> SourceDocument:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            document = _require_scoped_document(self._documents, requirement_id, document_id)
            _require_document_version(document, expected_version)
            if document.is_included == included and not document.requires_attention:
                return document
            updated = document.set_included(included)
            self._documents.save(updated)
            self._invalidation.for_changed_requirement(requirement_id)
            return updated

    def for_draft(
        self,
        actor: ActorProfile,
        draft_id: RequirementId,
        document_id: DocumentId,
        included: bool,
        expected_version: int,
    ) -> SourceDocument:
        with self._transactions.transaction():
            self._transactions.lock_requirement(draft_id)
            self._authorization.require_draft_owner(draft_id, actor)
            document = _require_draft_document(self._documents, draft_id, document_id)
            _require_document_version(document, expected_version)
            if document.is_included == included and not document.requires_attention:
                return document
            updated = document.set_included(included)
            self._documents.save(updated)
            return updated


class SetHiddenWorksheetInclusion:
    def __init__(
        self,
        documents: DocumentRepositoryPort,
        invalidation: InvalidateDerivedArtifacts,
        transactions: TransactionManagerPort,
        *,
        authorization: RequirementAccessService,
    ) -> None:
        self._authorization = authorization
        self._documents = documents
        self._invalidation = invalidation
        self._transactions = transactions

    def execute(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        document_id: DocumentId,
        worksheet_names: tuple[str, ...],
        expected_version: int,
    ) -> SourceDocument:
        return self._authorization.execute_mutation(
            requirement_id,
            actor,
            RequirementPermission.MEMBER,
            lambda: self._execute(
                requirement_id=requirement_id,
                document_id=document_id,
                worksheet_names=worksheet_names,
                expected_version=expected_version,
            ),
        )

    def _execute(
        self,
        requirement_id: RequirementId,
        document_id: DocumentId,
        worksheet_names: tuple[str, ...],
        expected_version: int,
    ) -> SourceDocument:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            document = _require_scoped_document(self._documents, requirement_id, document_id)
            _require_document_version(document, expected_version)
            updated = document.select_hidden_worksheets(worksheet_names)
            if updated == document:
                return document
            self._documents.save(updated)
            if document.is_included:
                self._invalidation.for_changed_requirement(requirement_id)
            return updated


class RemoveDocument:
    def __init__(
        self,
        documents: DocumentRepositoryPort,
        invalidation: InvalidateDerivedArtifacts,
        transactions: TransactionManagerPort,
        *,
        authorization: RequirementAccessService,
    ) -> None:
        self._authorization = authorization
        self._documents = documents
        self._invalidation = invalidation
        self._transactions = transactions

    def execute(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        document_id: DocumentId,
        expected_version: int,
    ) -> SourceDocument:
        return self._authorization.execute_mutation(
            requirement_id,
            actor,
            RequirementPermission.MEMBER,
            lambda: self._execute(
                requirement_id=requirement_id,
                document_id=document_id,
                expected_version=expected_version,
            ),
        )

    def _execute(
        self, requirement_id: RequirementId, document_id: DocumentId, expected_version: int
    ) -> SourceDocument:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            document = _require_scoped_document(self._documents, requirement_id, document_id)
            _require_document_version(document, expected_version)
            affected_analysis = document.is_included
            removed = document.remove()
            self._documents.save(removed)
            if affected_analysis:
                self._invalidation.for_changed_requirement(requirement_id)
            return removed

    def for_draft(
        self,
        actor: ActorProfile,
        draft_id: RequirementId,
        document_id: DocumentId,
        expected_version: int,
    ) -> SourceDocument:
        with self._transactions.transaction():
            self._transactions.lock_requirement(draft_id)
            self._authorization.require_draft_owner(draft_id, actor)
            document = _require_draft_document(self._documents, draft_id, document_id)
            _require_document_version(document, expected_version)
            updated = document.remove()
            self._documents.save(updated)
            return updated


class AssembleAnalysisDocuments:
    def __init__(
        self,
        documents: DocumentRepositoryPort,
        storage: DocumentStoragePort,
        extractor: DocumentExtractorPort,
        max_characters: int,
    ) -> None:
        self._documents = documents
        self._storage = storage
        self._extractor = extractor
        self._max_characters = max_characters

    def selection_snapshot(self, requirement_id: RequirementId) -> tuple[SourceDocument, ...]:
        """Read source metadata without extracting bytes or invoking a provider."""
        return tuple(
            sorted(
                self._documents.list_for_requirement(requirement_id), key=lambda item: item.id.value
            )
        )

    def eligibility(self, requirement: Requirement) -> AnalysisEligibility:
        return source_eligibility(requirement, self.selection_snapshot(requirement.id))

    def execute(self, requirement_id: RequirementId) -> AnalysisDocumentSelection:
        contexts: list[AnalysisDocumentContext] = []
        references: list[AnalysisDocumentReference] = []
        total = 0
        for document in self._documents.list_for_requirement(requirement_id):
            if not document.is_included or document.included_version_id is None:
                continue
            version = document.version(document.included_version_id)
            selected_blocks = document.included_blocks
            text = (
                "\n".join(block.text for block in selected_blocks if block.text)
                if version.extraction_version is not None
                else version.extracted_text or ""
            )
            total += len(text) if version.extraction_version is None else 0
            if total > self._max_characters:
                raise DocumentContextTooLargeError(
                    "Selected document text exceeds the configured analysis context window; "
                    "exclude a document and try again."
                )
            contexts.append(
                AnalysisDocumentContext(
                    document_id=document.id.value,
                    version_id=version.id.value,
                    filename=version.filename,
                    checksum_sha256=version.checksum_sha256,
                    extracted_text=text,
                    extraction_version=version.extraction_version or "legacy-plain-text",
                    evidence_blocks=[
                        {
                            "block_id": block.id,
                            "kind": block.kind.value,
                            "section_path": list(block.section_path),
                            "label": block.label,
                            "text": block.text,
                            "asset_id": block.asset_id,
                        }
                        for block in selected_blocks
                    ],
                    image_assets=[
                        {
                            "asset_id": asset.id,
                            "block_id": asset.block_id,
                            "mime_type": asset.mime_type,
                            "content": self._extractor.extract_asset(
                                version.mime_type,
                                self._storage.get(version.id),
                                asset.package_path,
                            ),
                        }
                        for asset in version.assets
                        if asset.block_id in {block.id for block in selected_blocks}
                    ],
                )
            )
            references.append(
                AnalysisDocumentReference(
                    document.id.value,
                    version.id.value,
                    version.filename,
                    version.checksum_sha256,
                )
            )
        return AnalysisDocumentSelection(tuple(contexts), tuple(references))


def _require_scoped_document(
    documents: DocumentRepositoryPort,
    requirement_id: RequirementId,
    document_id: DocumentId,
) -> SourceDocument:
    document = documents.get(document_id)
    if document is None or document.removed or document.requirement_id != requirement_id:
        raise DocumentNotFoundError("Document was not found for this Requirement.")
    return document


def _require_draft_document(
    documents: DocumentRepositoryPort, draft_id: RequirementId, document_id: DocumentId
) -> SourceDocument:
    document = documents.get(document_id)
    if document is None or document.removed or document.draft_id != draft_id:
        raise DocumentNotFoundError("Document was not found for this draft.")
    return document


def _require_document_version(document: SourceDocument, expected_version: int) -> None:
    if document.version_number != expected_version:
        raise DocumentVersionConflictError(
            f"Document {document.id.value!r} is at version {document.version_number}; "
            f"received {expected_version}."
        )
