"""The reference library's background worker. Scanning is platform-kernel's (ADR-0100)."""

from __future__ import annotations

from smb_kernel.documents.scanner import ClamAvDocumentScanner as ClamAvDocumentScanner
from smb_kernel.documents.scanner import OfflineDocumentScanner as OfflineDocumentScanner

from smb_requirement_agent.application.use_cases.document_library import DocumentLibrary
from smb_requirement_agent.application.use_cases.reference_knowledge import ReferenceKnowledge
from smb_requirement_agent.infrastructure.documents.ingestion_loop import IngestionLoop


class DocumentIngestionWorker(IngestionLoop):
    """Scans and extracts library sources, then indexes their publications."""

    def __init__(self, library: DocumentLibrary, knowledge: ReferenceKnowledge) -> None:
        super().__init__("document-ingestion", (library.process_next, knowledge.index_next))
