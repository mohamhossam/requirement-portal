"""Requirement attachments' background worker, apart from the library's (ADR-0099)."""

from collections.abc import Callable

from smb_requirement_agent.infrastructure.documents.ingestion_loop import IngestionLoop
from smb_requirement_agent.requirements.application.use_cases.attachment_ingestion import (
    AttachmentIngestion,
)


class AttachmentIngestionWorker(IngestionLoop):
    """Scans and extracts attachment uploads, then attaches them to their Requirement."""

    def __init__(
        self,
        attachments: AttachmentIngestion,
        *,
        failed: Callable[[], None],
        shutdown_grace_seconds: float,
        monotonic_seconds: Callable[[], float],
    ) -> None:
        super().__init__(
            "attachment-ingestion",
            (attachments.process_next,),
            failed=failed,
            shutdown_grace_seconds=shutdown_grace_seconds,
            monotonic_seconds=monotonic_seconds,
        )
