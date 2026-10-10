"""HTTP schemas for source-document review."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from smb_requirement_agent.interfaces.api.schemas.bounds import (
    MAX_CATALOGUE_ITEMS,
    Name,
)
from smb_requirement_agent.requirements.domain.document.value_objects import (
    AnalysisReadiness,
    EvidenceBlockKind,
    ExtractionStatus,
    ExtractionWarningSeverity,
)


class DocumentEvidenceSummaryResponse(BaseModel):
    section_count: int
    table_count: int
    image_count: int
    worksheet_count: int
    block_count: int


class DocumentExtractionWarningResponse(BaseModel):
    code: str
    severity: ExtractionWarningSeverity
    message: str
    block_id: str | None


class DocumentEvidenceBlockResponse(BaseModel):
    id: str
    kind: EvidenceBlockKind
    ordinal: int
    section_path: list[str]
    label: str
    text: str | None
    asset_id: str | None


class DocumentVersionMetadataResponse(BaseModel):
    id: str
    number: int
    filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    extraction_status: ExtractionStatus
    extraction_error: str | None
    created_at: datetime
    analysis_readiness: AnalysisReadiness
    evidence_summary: DocumentEvidenceSummaryResponse
    extraction_warnings: list[DocumentExtractionWarningResponse]


class DocumentSummaryResponse(BaseModel):
    id: str
    version: int
    requirement_id: str | None
    draft_id: str | None
    requires_attention: bool = False
    included_in_analysis: bool
    included_version_id: str | None
    version_count: int
    current_version: DocumentVersionMetadataResponse
    hidden_worksheets: list[str] = []
    included_hidden_worksheets: list[str] = []


class DocumentVersionDetailResponse(DocumentVersionMetadataResponse):
    extracted_text: str | None
    extraction_version: str | None
    evidence_blocks: list[DocumentEvidenceBlockResponse]


class DocumentDetailResponse(DocumentSummaryResponse):
    versions: list[DocumentVersionDetailResponse]


class DocumentOwnerResponse(BaseModel):
    """The Requirement or draft a document is attached to; its title, if it still exists."""

    kind: Literal["requirement", "draft"]
    id: str
    title: str | None


class DocumentListItemResponse(DocumentSummaryResponse):
    owner: DocumentOwnerResponse


class DocumentCountsResponse(BaseModel):
    """As the documents page groups them; a document blocking analysis counts only there."""

    attention: int
    included: int
    excluded: int


class DocumentListResponse(BaseModel):
    """One page of documents (production hardening PR 13). The counts and owners cover every
    document the actor may open, whatever the search or filter."""

    documents: list[DocumentListItemResponse]
    total: int
    offset: int
    limit: int
    has_more: bool
    counts: DocumentCountsResponse
    owners: list[DocumentOwnerResponse]


class OwnedDocumentDetailResponse(DocumentDetailResponse):
    owner: DocumentOwnerResponse


class DocumentContentResponse(BaseModel):
    document_id: str
    version_id: str
    filename: str
    extracted_text: str


class SetDocumentInclusionRequest(BaseModel):
    included: bool
    expected_version: int = Field(ge=1)


class SetHiddenWorksheetInclusionRequest(BaseModel):
    worksheet_names: list[Name] = Field(max_length=MAX_CATALOGUE_ITEMS)
    expected_version: int = Field(ge=1)
