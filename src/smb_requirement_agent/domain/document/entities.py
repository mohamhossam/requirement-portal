"""Requirement-scoped supporting documents with immutable file versions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from smb_kernel.documents.model import DocumentAsset as DocumentAsset
from smb_kernel.documents.model import DocumentEvidenceBlock as DocumentEvidenceBlock
from smb_kernel.documents.model import (
    DocumentExtractionWarning as DocumentExtractionWarning,
)

from smb_requirement_agent.domain.document.errors import (
    DocumentInclusionError,
    InvalidDocumentError,
)
from smb_requirement_agent.domain.document.value_objects import (
    AnalysisReadiness,
    DocumentId,
    DocumentVersionId,
    EvidenceBlockKind,
    ExtractionStatus,
    ExtractionWarningSeverity,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.domain.shared.staleness import require_aware


@dataclass(frozen=True)
class SourceDocumentVersion:
    id: DocumentVersionId
    number: int
    filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    extraction_status: ExtractionStatus
    created_at: datetime
    extracted_text: str | None = None
    extraction_error: str | None = None
    extraction_version: str | None = None
    evidence_blocks: tuple[DocumentEvidenceBlock, ...] = ()
    extraction_warnings: tuple[DocumentExtractionWarning, ...] = ()
    assets: tuple[DocumentAsset, ...] = ()

    def __post_init__(self) -> None:
        filename = self.filename.strip()
        mime_type = self.mime_type.strip().lower()
        checksum = self.checksum_sha256.strip().lower()
        if not filename or not mime_type or self.number < 1 or self.size_bytes < 1:
            raise InvalidDocumentError("Document version metadata is incomplete.")
        if len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum):
            raise InvalidDocumentError("Document checksum must be a SHA-256 hex digest.")
        require_aware(self.created_at, "document created_at")
        if self.extraction_status is ExtractionStatus.READY:
            if not (self.extracted_text or "").strip() and not any(
                block.kind is EvidenceBlockKind.IMAGE and block.asset_id
                for block in self.evidence_blocks
            ):
                raise InvalidDocumentError("A ready document must contain text or image evidence.")
            if self.extraction_error is not None:
                raise InvalidDocumentError("A ready document cannot contain an extraction error.")
        elif not (self.extraction_error or "").strip():
            raise InvalidDocumentError("A failed document must explain the extraction error.")
        object.__setattr__(self, "filename", filename)
        object.__setattr__(self, "mime_type", mime_type)
        object.__setattr__(self, "checksum_sha256", checksum)
        if self.extracted_text is not None:
            object.__setattr__(self, "extracted_text", self.extracted_text.strip())
        if self.extraction_version is not None:
            version = self.extraction_version.strip()
            object.__setattr__(self, "extraction_version", version or None)
        block_ids = tuple(item.id for item in self.evidence_blocks)
        if len(block_ids) != len(set(block_ids)):
            raise InvalidDocumentError("Document evidence block IDs must be unique.")
        if self.evidence_blocks and tuple(item.ordinal for item in self.evidence_blocks) != tuple(
            range(1, len(self.evidence_blocks) + 1)
        ):
            raise InvalidDocumentError("Document evidence block ordinals must be contiguous.")
        asset_ids = tuple(item.id for item in self.assets)
        if len(asset_ids) != len(set(asset_ids)):
            raise InvalidDocumentError("Document asset IDs must be unique.")
        known_blocks = set(block_ids)
        if any(item.block_id not in known_blocks for item in self.assets):
            raise InvalidDocumentError("Document assets must reference an evidence block.")
        if any(
            item.block_id is not None and item.block_id not in known_blocks
            for item in self.extraction_warnings
        ):
            raise InvalidDocumentError("Extraction warnings must reference a known block.")

    @property
    def analysis_readiness(self) -> AnalysisReadiness:
        if self.extraction_status is ExtractionStatus.FAILED or any(
            item.severity is ExtractionWarningSeverity.BLOCKING for item in self.extraction_warnings
        ):
            return AnalysisReadiness.BLOCKED
        if self.extraction_warnings or self.extraction_version is None:
            return AnalysisReadiness.READY_WITH_WARNINGS
        return AnalysisReadiness.READY


@dataclass(frozen=True)
class SourceDocument:
    id: DocumentId
    versions: tuple[SourceDocumentVersion, ...]
    requirement_id: RequirementId | None = None
    draft_id: RequirementId | None = None
    included_version_id: DocumentVersionId | None = None
    removed: bool = False
    included_hidden_worksheets: tuple[str, ...] = ()
    version_number: int = 1
    requires_attention: bool = False

    def __post_init__(self) -> None:
        if self.version_number < 1:
            raise InvalidDocumentError("Document aggregate version must be positive.")
        if (self.requirement_id is None) == (self.draft_id is None):
            raise InvalidDocumentError(
                "A document must belong to exactly one Requirement or Requirement draft."
            )
        if not self.versions:
            raise InvalidDocumentError("A document must contain at least one immutable version.")
        expected = tuple(range(1, len(self.versions) + 1))
        if tuple(item.number for item in self.versions) != expected:
            raise InvalidDocumentError("Document version numbers must be contiguous.")
        if self.included_version_id is not None:
            selected = self.version(self.included_version_id)
            if self.removed or selected.extraction_status is not ExtractionStatus.READY:
                raise DocumentInclusionError(
                    "Only an active, successfully extracted version can be included in analysis."
                )
        cleaned_sheets = tuple(
            sorted({item.strip() for item in self.included_hidden_worksheets if item.strip()})
        )
        object.__setattr__(self, "included_hidden_worksheets", cleaned_sheets)

    @property
    def current_version(self) -> SourceDocumentVersion:
        return self.versions[-1]

    @property
    def is_included(self) -> bool:
        return self.included_version_id is not None and not self.removed

    def version(self, version_id: DocumentVersionId) -> SourceDocumentVersion:
        for version in self.versions:
            if version.id == version_id:
                return version
        raise InvalidDocumentError(
            f"Document version {version_id.value!r} does not belong to this document."
        )

    @property
    def included_blocks(self) -> tuple[DocumentEvidenceBlock, ...]:
        """The included version's blocks, without hidden worksheets nobody chose to include.

        Analysis and the requirement knowledge index both read a document through this, so
        they always agree on what it contributes. Empty when the document is not included.
        """
        if not self.is_included or self.included_version_id is None:
            return ()
        return tuple(
            block
            for block in self.version(self.included_version_id).evidence_blocks
            if not block.section_path
            or not block.section_path[0].startswith("Hidden worksheet: ")
            or block.section_path[0].removeprefix("Hidden worksheet: ")
            in self.included_hidden_worksheets
        )

    def add_version(self, version: SourceDocumentVersion) -> SourceDocument:
        if self.removed:
            raise InvalidDocumentError("A removed document cannot receive a new version.")
        if version.number != len(self.versions) + 1:
            raise InvalidDocumentError("The next immutable document version number is invalid.")
        return replace(
            self,
            versions=(*self.versions, version),
            included_version_id=None,
            included_hidden_worksheets=(),
            requires_attention=False,
            version_number=self.version_number + 1,
        )

    def select_hidden_worksheets(self, names: tuple[str, ...]) -> SourceDocument:
        available = {
            item.section_path[0].removeprefix("Hidden worksheet: ")
            for item in self.current_version.evidence_blocks
            if item.section_path and item.section_path[0].startswith("Hidden worksheet: ")
        }
        selected = {item.strip() for item in names if item.strip()}
        if not selected.issubset(available):
            raise DocumentInclusionError("One or more hidden worksheets do not exist.")
        return replace(
            self,
            included_hidden_worksheets=tuple(sorted(selected)),
            version_number=self.version_number + 1,
        )

    def set_included(self, included: bool) -> SourceDocument:
        if self.removed:
            raise DocumentInclusionError("A removed document cannot be included in analysis.")
        selected = self.current_version
        if included and selected.extraction_status is not ExtractionStatus.READY:
            raise DocumentInclusionError(
                "The current document version cannot be included because extraction failed."
            )
        if included and selected.analysis_readiness is AnalysisReadiness.BLOCKED:
            raise DocumentInclusionError(
                "This document has blocking extraction warnings and cannot be analyzed."
            )
        return replace(
            self,
            included_version_id=selected.id if included else None,
            requires_attention=False,
            version_number=self.version_number + 1,
        )

    def remove(self) -> SourceDocument:
        return replace(
            self,
            included_version_id=None,
            removed=True,
            version_number=self.version_number + 1,
        )

    def attach_to_requirement(self, requirement_id: RequirementId) -> SourceDocument:
        return replace(
            self,
            requirement_id=requirement_id,
            draft_id=None,
            version_number=self.version_number + 1,
        )
