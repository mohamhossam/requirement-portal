"""The stages a scanned, extracted upload passes through.

Both the reference library and requirement attachments ingest files this way, so
the vocabulary sits outside both contexts (ADR-0099).
"""

from enum import StrEnum


class IngestionStage(StrEnum):
    QUEUED = "queued"
    SCANNING = "scanning"
    EXTRACTING = "extracting"
    READY = "ready_for_review"
    FAILED = "failed"
    QUARANTINED = "quarantined"
    CANCELLED = "cancelled"


STOPPED_STAGES = frozenset(
    {IngestionStage.FAILED, IngestionStage.QUARANTINED, IngestionStage.CANCELLED}
)
IN_PROGRESS_STAGES = frozenset(
    {IngestionStage.QUEUED, IngestionStage.SCANNING, IngestionStage.EXTRACTING}
)
