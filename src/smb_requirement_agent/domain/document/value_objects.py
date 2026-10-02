"""Value objects for immutable source-document versions."""

from dataclasses import dataclass
from enum import StrEnum

from smb_requirement_agent.domain.document.errors import InvalidDocumentError


@dataclass(frozen=True)
class DocumentId:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise InvalidDocumentError("Document ID must not be blank.")


@dataclass(frozen=True)
class DocumentVersionId:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise InvalidDocumentError("Document version ID must not be blank.")


class ExtractionStatus(StrEnum):
    READY = "ready"
    FAILED = "failed"


class EvidenceBlockKind(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE_ROW = "table_row"
    IMAGE = "image"
    WORKSHEET_RANGE = "worksheet_range"
    EXTERNAL_REFERENCE = "external_reference"


class ExtractionWarningSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class AnalysisReadiness(StrEnum):
    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    BLOCKED = "blocked"
