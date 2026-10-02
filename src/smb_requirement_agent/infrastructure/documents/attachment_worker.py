"""Requirement attachments' background worker, apart from the library's (ADR-0099)."""

from smb_requirement_agent.application.use_cases.attachment_ingestion import AttachmentIngestion
from smb_requirement_agent.infrastructure.documents.ingestion_loop import IngestionLoop


class AttachmentIngestionWorker(IngestionLoop):
    """Scans and extracts attachment uploads, then attaches them to their Requirement."""

    def __init__(self, attachments: AttachmentIngestion) -> None:
        super().__init__("attachment-ingestion", (attachments.process_next,))
