"""Independent document worker and fail-closed local malware scanning."""

from __future__ import annotations

import logging
import socket
import struct
from threading import Event, Thread

from smb_requirement_agent.application.errors import DocumentExtractionError
from smb_requirement_agent.application.use_cases.attachment_ingestion import AttachmentIngestion
from smb_requirement_agent.application.use_cases.document_library import DocumentLibrary
from smb_requirement_agent.application.use_cases.reference_knowledge import ReferenceKnowledge


class ClamAvDocumentScanner:
    def __init__(self, host: str, port: int) -> None:
        self._host, self._port = host, port

    def scan(self, content: bytes) -> bool:
        try:
            with socket.create_connection((self._host, self._port), timeout=30) as connection:
                connection.sendall(b"zINSTREAM\x00")
                for start in range(0, len(content), 65536):
                    chunk = content[start : start + 65536]
                    connection.sendall(struct.pack("!I", len(chunk)) + chunk)
                connection.sendall(struct.pack("!I", 0))
                reply = b""
                while b"\x00" not in reply and len(reply) < 4096:
                    part = connection.recv(4096 - len(reply))
                    if not part:
                        break
                    reply += part
        except OSError as exc:
            raise DocumentExtractionError(
                "Malware scanner unavailable. Restore the local scanner and retry."
            ) from exc
        result = reply.split(b"\x00", 1)[0]
        if result == b"stream: OK" and b"\x00" in reply:
            return True
        if result.startswith(b"stream: ") and result.endswith(b" FOUND"):
            return False
        raise DocumentExtractionError(
            "Malware scanner did not return a complete clean verdict. "
            "Retry after checking its limits."
        )


class OfflineDocumentScanner:
    """Explicit deterministic development adapter, never selected for durable/OIDC deployments."""

    def scan(self, content: bytes) -> bool:
        return b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" not in content


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
