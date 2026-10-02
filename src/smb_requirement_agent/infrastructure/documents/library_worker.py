"""Independent document worker. Scanning is platform-kernel's (ADR-0100)."""

from __future__ import annotations

import logging
from threading import Event, Thread

from smb_kernel.documents.scanner import ClamAvDocumentScanner as ClamAvDocumentScanner
from smb_kernel.documents.scanner import OfflineDocumentScanner as OfflineDocumentScanner

from smb_requirement_agent.application.use_cases.attachment_ingestion import AttachmentIngestion
from smb_requirement_agent.application.use_cases.document_library import DocumentLibrary
from smb_requirement_agent.application.use_cases.reference_knowledge import ReferenceKnowledge


class DocumentIngestionWorker:
    def __init__(
        self,
        library: DocumentLibrary,
        knowledge: ReferenceKnowledge,
        attachments: AttachmentIngestion,
    ) -> None:
        self._attachments = attachments
        self._library = library
        self._knowledge = knowledge
        self._stop = Event()
        self._thread: Thread | None = None

    @property
    def healthy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        self._stop.clear()
        self._thread = Thread(target=self._run, name="document-ingestion", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                worked = self._library.process_next()
                attached = self._attachments.process_next()
                indexed = self._knowledge.index_next()
                worked = worked or indexed or attached
            except Exception as exc:
                # Top-level boundary: keep durable leases recoverable; never log document bodies.
                logging.getLogger(__name__).error("Document worker failed: %s", type(exc).__name__)
                worked = False
            if not worked:
                self._stop.wait(1)

    def stop(self) -> bool:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        return not self.healthy

    def wait_until_stopped(self) -> None:
        if self._thread is not None:
            self._thread.join()
