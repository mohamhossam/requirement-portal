"""Durable scanned attachment uploads, finalized atomically through UploadDocument."""

from dataclasses import dataclass, replace

from smb_requirement_agent.application.errors import (
    DocumentNotFoundError,
    DocumentVersionConflictError,
    PersistenceError,
    RequirementDraftNotFoundError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.document_extractor import ExtractedDocument
from smb_requirement_agent.application.ports.document_library import DocumentLibraryPort
from smb_requirement_agent.application.ports.document_storage import DocumentStoragePort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.document_library import DocumentLibrary
from smb_requirement_agent.application.use_cases.documents import (
    UploadDocument,
    UploadDocumentInput,
)
from smb_requirement_agent.application.use_cases.identity_access import RequirementAccessService
from smb_requirement_agent.domain.document.errors import InvalidDocumentError
from smb_requirement_agent.domain.document.library import (
    AttachmentTarget,
    IngestionStage,
    LibraryDocument,
)
from smb_requirement_agent.domain.document.value_objects import DocumentId, DocumentVersionId
from smb_requirement_agent.domain.identity.entities import ActorProfile
from smb_requirement_agent.domain.identity.errors import AuthorizationDeniedError
from smb_requirement_agent.domain.requirement.value_objects import RequirementId


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
        library: DocumentLibrary,
        repository: DocumentLibraryPort,
        storage: DocumentStoragePort,
        upload: UploadDocument,
        access: RequirementAccessService,
        transactions: TransactionManagerPort,
    ) -> None:
        self._library = library
        self._repository = repository
        self._storage = storage
        self._upload = upload
        self._access = access
        self._transactions = transactions

    @property
    def max_file_bytes(self) -> int:
        return self._library.max_file_bytes

    def _authorize(self, target: AttachmentTarget, actor: ActorProfile) -> None:
        source_id = RequirementId(target.source_id)
        if target.is_draft:
            self._access.require_draft_owner(source_id, actor)
        else:
            self._access.require_requirement_member(source_id, actor)

    @staticmethod
    def _view(document: LibraryDocument) -> AttachmentIngestionView:
        source = document.versions[-1]
        return AttachmentIngestionView(
            document.id,
            document.version,
            source.filename,
            source.stage,
            source.error,
            document.attached_document_id,
            document.attachment_excluded,
        )

    def list(
        self, source_id: str, is_draft: bool, actor: ActorProfile
    ) -> tuple[AttachmentIngestionView, ...]:
        self._authorize(AttachmentTarget(source_id, is_draft, False), actor)
        return tuple(self._view(d) for d in self._repository.list_attachments(source_id, is_draft))

    def submit(
        self, target: AttachmentTarget, data: UploadDocumentInput, key: str, actor: ActorProfile
    ) -> AttachmentIngestionView:
        with self._transactions.transaction():
            self._transactions.lock_requirement(RequirementId(target.source_id))
            self._authorize(target, actor)
            document = self._library.submit(
                data.filename[:200], data, key, actor, attachment_target=target
            )
            return self._view(document)

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
            document = self._repository.get(ingestion_id)
            if (
                document is None
                or document.attachment_target is None
                or document.attachment_target.source_id != source_id
                or document.attachment_target.is_draft != is_draft
            ):
                raise DocumentNotFoundError("Attachment upload was not found.")
            if document.version != expected:
                raise DocumentVersionConflictError("Processing changed. Reload its status.")
            source = document.versions[-1]
            if retry is None:
                if (
                    source.stage
                    not in {
                        IngestionStage.FAILED,
                        IngestionStage.QUARANTINED,
                        IngestionStage.CANCELLED,
                    }
                    or document.attached_document_id is not None
                ):
                    raise DocumentVersionConflictError("Only stopped uploads can be excluded.")
                updated = replace(document, attachment_excluded=True, version=document.version + 1)
                self._repository.save(updated, document.version)
                return self._view(updated)
            eligible = (
                {IngestionStage.FAILED, IngestionStage.CANCELLED}
                if retry
                else {
                    IngestionStage.QUEUED,
                    IngestionStage.SCANNING,
                    IngestionStage.EXTRACTING,
                }
            )
            if source.stage not in eligible or document.attached_document_id is not None:
                raise DocumentVersionConflictError("Processing state does not allow this action.")
            updated = document.update_file(
                replace(
                    source,
                    stage=IngestionStage.QUEUED if retry else IngestionStage.CANCELLED,
                    attempt=0 if retry else source.attempt,
                    lease_token=None,
                    lease_until=None,
                    error=None,
                )
            )
            updated = replace(updated, attachment_excluded=False)
            self._repository.save(updated, document.version)
            return self._view(updated)

    def process_next(self) -> bool:
        pending = self._repository.pending_attachment()
        if pending is None:
            return False
        target = pending.attachment_target
        if target is None:
            raise PersistenceError("A pending attachment was stored without its target.")
        with self._transactions.transaction():
            self._transactions.lock_requirement(RequirementId(target.source_id))
            document = self._repository.get(pending.id)
            if document is None or document.version != pending.version:
                return True
            source = document.versions[-1]
            actor = ActorProfile(
                document.owner.id, document.owner.display_name, document.owner.email
            )
            try:
                self._authorize(target, actor)
                extraction = ExtractedDocument(
                    "\n\n".join(b.text for b in source.blocks if b.text),
                    source.extraction_version or "unknown",
                    source.blocks,
                    source.warning_details,
                    source.assets,
                )
                attached = self._upload.accept_extraction(
                    UploadDocumentInput(
                        source.filename,
                        source.mime_type,
                        self._storage.get(DocumentVersionId(source.id)),
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
                updated = document.update_file(
                    replace(
                        source,
                        stage=IngestionStage.FAILED,
                        error="Attachment source or access changed. "
                        "Reload the source before retrying.",
                    )
                )
            else:
                updated = replace(
                    document, attached_document_id=attached.id.value, version=document.version + 1
                )
            self._repository.save(updated, document.version)
        return True
