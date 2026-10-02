"""Value objects for immutable source-document versions.

The extraction vocabulary is platform-kernel's, re-exported (ADR-0100).
"""

from dataclasses import dataclass
from enum import StrEnum

from smb_kernel.documents.model import DocumentVersionId as DocumentVersionId
from smb_kernel.documents.model import EvidenceBlockKind as EvidenceBlockKind
from smb_kernel.documents.model import (
    ExtractionWarningSeverity as ExtractionWarningSeverity,
)

from smb_requirement_agent.domain.document.errors import InvalidDocumentError


@dataclass(frozen=True)
class DocumentId:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise InvalidDocumentError("Document ID must not be blank.")


class ExtractionStatus(StrEnum):
    READY = "ready"
    FAILED = "failed"


class AnalysisReadiness(StrEnum):
    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    BLOCKED = "blocked"
