"""Documents: requirement attachments, the governed source library and their extraction."""

from __future__ import annotations

import multiprocessing
from dataclasses import dataclass

from smb_kernel.documents.bounded_extractor import (
    BoundedSubprocessDocumentExtractor,
    ExtractionLimits,
)
from smb_kernel.documents.process_resources import (
    child_process_resource_limiter,
)
from smb_kernel.documents.scanner import ClamAvDocumentScanner, OfflineDocumentScanner
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.domain_events import DomainEventPublisher
from smb_requirement_agent.application.use_cases.analysis_documents import AssembleAnalysisDocuments
from smb_requirement_agent.application.use_cases.attachment_ingestion import AttachmentIngestion
from smb_requirement_agent.application.use_cases.documents import (
    GetDocument,
    ListDocuments,
    RemoveDocument,
    SetDocumentInclusion,
    SetHiddenWorksheetInclusion,
    UploadDocument,
)
from smb_requirement_agent.application.use_cases.identity_access import RequirementAccessService
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.documents.attachment_worker import (
    AttachmentIngestionWorker,
)
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters

# Library sources are extracted one at a time in the background, so they get a
# far larger allowance than a request-time attachment.
_BACKGROUND_EXTRACTION_SECONDS = 600
_BACKGROUND_EXTRACTION_MEMORY_BYTES = 4 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class DocumentWiring:
    extractor: BoundedSubprocessDocumentExtractor
    analysis_documents: AssembleAnalysisDocuments
    upload: UploadDocument
    attachment_ingestion: AttachmentIngestion
    attachment_worker: AttachmentIngestionWorker
    list_documents: ListDocuments
    get_document: GetDocument
    set_inclusion: SetDocumentInclusion
    set_hidden_worksheet_inclusion: SetHiddenWorksheetInclusion
    remove: RemoveDocument


def build_documents(
    settings: Settings,
    persistence: PersistenceAdapters,
    clock: ClockPort,
    events: DomainEventPublisher,
    access: RequirementAccessService,
) -> DocumentWiring:
    extractor = BoundedSubprocessDocumentExtractor(
        concurrency=settings.document_extraction_concurrency,
        waiting_requests=settings.document_extraction_queue,
        deadline_seconds=settings.document_extraction_timeout_seconds,
        memory_bytes=settings.document_extraction_memory_bytes,
        limits=ExtractionLimits(
            pdf_pages=settings.document_max_pdf_pages,
            characters=settings.document_max_extracted_characters,
            xml_nodes=settings.document_max_xml_nodes,
            image_pixels=settings.document_max_image_pixels,
            spreadsheet_cells=settings.document_max_spreadsheet_cells,
        ),
        resource_limiter=child_process_resource_limiter(),
        process_context=multiprocessing.get_context("spawn"),
    )
    # Attachments are extracted in the background, one large extraction at a time.
    background_extractor = _background_extractor(settings)
    scanner = (
        OfflineDocumentScanner()
        if settings.library_scan_mode == "offline"
        else ClamAvDocumentScanner(settings.library_scanner_host, settings.library_scanner_port)
    )
    upload = UploadDocument(
        persistence.document_repository,
        persistence.document_storage,
        extractor,
        persistence.requirement_repository,
        persistence.requirement_draft_repository,
        events,
        persistence.transaction_manager,
        access,
        clock,
        settings.document_max_file_bytes,
    )
    attachment_ingestion = AttachmentIngestion(
        persistence.attachment_ingestions,
        persistence.document_storage,
        scanner,
        background_extractor,
        upload,
        access,
        persistence.transaction_manager,
        clock,
        settings.document_max_file_bytes,
    )
    return DocumentWiring(
        extractor=extractor,
        analysis_documents=AssembleAnalysisDocuments(
            persistence.document_repository,
            persistence.document_storage,
            extractor,
            settings.document_context_max_characters,
        ),
        upload=upload,
        attachment_ingestion=attachment_ingestion,
        attachment_worker=AttachmentIngestionWorker(attachment_ingestion),
        list_documents=ListDocuments(persistence.document_repository, access),
        get_document=GetDocument(
            persistence.document_repository,
            persistence.document_storage,
            extractor,
            access,
        ),
        set_inclusion=SetDocumentInclusion(
            persistence.document_repository,
            events,
            persistence.transaction_manager,
            authorization=access,
        ),
        set_hidden_worksheet_inclusion=SetHiddenWorksheetInclusion(
            persistence.document_repository,
            events,
            persistence.transaction_manager,
            authorization=access,
        ),
        remove=RemoveDocument(
            persistence.document_repository,
            events,
            persistence.transaction_manager,
            authorization=access,
        ),
    )


def _background_extractor(settings: Settings) -> BoundedSubprocessDocumentExtractor:
    return BoundedSubprocessDocumentExtractor(
        concurrency=1,
        waiting_requests=1,
        deadline_seconds=_BACKGROUND_EXTRACTION_SECONDS,
        memory_bytes=_BACKGROUND_EXTRACTION_MEMORY_BYTES,
        limits=ExtractionLimits(
            ocr_artifacts_path=settings.library_ocr_artifacts_path,
            office_preview_executable=settings.document_office_preview_executable,
            pdf_pages=settings.document_max_pdf_pages,
            characters=settings.document_max_extracted_characters,
            xml_nodes=settings.document_max_xml_nodes,
            image_pixels=settings.document_max_image_pixels,
            spreadsheet_cells=settings.document_max_spreadsheet_cells,
        ),
        resource_limiter=child_process_resource_limiter(),
        process_context=multiprocessing.get_context("spawn"),
    )
