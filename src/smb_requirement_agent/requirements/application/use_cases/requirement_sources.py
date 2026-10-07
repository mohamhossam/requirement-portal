"""Usable source policy shared by intake and analysis without reading blobs."""

from collections.abc import Sequence

from smb_requirement_agent.requirements.domain.document.entities import SourceDocument
from smb_requirement_agent.requirements.domain.document.value_objects import AnalysisReadiness
from smb_requirement_agent.requirements.domain.requirement.entities import (
    AnalysisEligibility,
    Requirement,
    RequirementDraft,
)
from smb_requirement_agent.requirements.domain.requirement.errors import (
    InvalidRequirementDescriptionError,
)


def has_usable_attachment(documents: Sequence[SourceDocument]) -> bool:
    return any(
        document.is_included
        and document.version(document.included_version_id).analysis_readiness
        is not AnalysisReadiness.BLOCKED
        for document in documents
        if document.included_version_id is not None
    )


def source_eligibility(
    source: Requirement | RequirementDraft, documents: Sequence[SourceDocument]
) -> AnalysisEligibility:
    eligibility = source.analysis_eligibility
    missing = eligibility.missing_fields
    if has_usable_attachment(documents):
        missing = tuple(field for field in missing if field != "description")
    if any(document.requires_attention and not document.removed for document in documents):
        missing = (*missing, "attachment_review")
    return AnalysisEligibility(not missing, missing)


def require_usable_source(text: str, documents: Sequence[SourceDocument]) -> None:
    if any(document.requires_attention and not document.removed for document in documents):
        raise InvalidRequirementDescriptionError(
            "Retry, remove, or explicitly exclude failed attachments."
        )
    if not text.strip() and not has_usable_attachment(documents):
        raise InvalidRequirementDescriptionError(
            "Describe the business need or include at least one ready attachment."
        )
