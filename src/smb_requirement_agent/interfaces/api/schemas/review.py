"""HTTP contracts for the Slice 8 breakdown review."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from smb_requirement_agent.governance.domain.review.entities import (
    BreakdownStatus,
    DependencyEvidenceKind,
    FlagCategory,
    FlagSeverity,
    FlagStatus,
    ResolutionPolicy,
    ReviewSourceKind,
)
from smb_requirement_agent.interfaces.api.schemas.bounds import (
    MAX_IDENTIFIER_CHARACTERS,
    MAX_TEXT_CHARACTERS,
)
from smb_requirement_agent.interfaces.api.schemas.governance import (
    ApprovalResponse,
    ReviewCommentResponse,
)
from smb_requirement_agent.interfaces.api.schemas.identity import ActorResponse
from smb_requirement_agent.interfaces.api.schemas.story import StoryQualityResponse

NonBlank = Annotated[str, Field(min_length=1, max_length=MAX_TEXT_CHARACTERS)]
NonBlankIdentifier = Annotated[str, Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)]


class ReviewSourceResponse(BaseModel):
    kind: ReviewSourceKind
    item_id: str
    label: str


class ReviewDependencyResponse(BaseModel):
    id: str
    description: str
    source: ReviewSourceResponse
    evidence_kind: DependencyEvidenceKind


class ReviewRiskResponse(BaseModel):
    id: str
    severity: FlagSeverity
    description: str
    source: ReviewSourceResponse


class ReviewFlagResponse(BaseModel):
    id: str
    category: FlagCategory
    severity: FlagSeverity
    title: str
    detail: str
    source: ReviewSourceResponse
    resolution_policy: ResolutionPolicy
    status: FlagStatus
    resolution_decision_id: str | None


class ReviewRecommendationResponse(BaseModel):
    id: str
    action: str
    rationale: str
    source: ReviewSourceResponse


class ReviewDecisionResponse(BaseModel):
    id: str
    decision: str
    rationale: str
    recorded_at: datetime
    target_flag_id: str | None
    recorded_by: ActorResponse | None


class BreakdownReviewResponse(BaseModel):
    requirement_id: str
    version: int
    generated_at: datetime
    ruleset_version: str
    evidence_fingerprint: str
    fresh: bool
    unresolved_blocker_count: int
    unresolved_warning_count: int
    dependencies: list[ReviewDependencyResponse]
    risks: list[ReviewRiskResponse]
    flags: list[ReviewFlagResponse]
    recommendations: list[ReviewRecommendationResponse]
    quality_assessments: list[StoryQualityResponse]
    decisions: list[ReviewDecisionResponse]
    status: BreakdownStatus
    submitted_fingerprint: str | None
    approval_history: list[ApprovalResponse]
    comments: list[ReviewCommentResponse]
    model_config = ConfigDict(frozen=True)


class DecisionRequest(BaseModel):
    decision: NonBlankIdentifier
    rationale: NonBlank
    expected_fingerprint: NonBlankIdentifier
    expected_version: int = Field(ge=1)
    target_flag_id: NonBlankIdentifier | None = None


class ResolveFlagRequest(BaseModel):
    decision: NonBlankIdentifier
    rationale: NonBlank
    expected_fingerprint: NonBlankIdentifier
    expected_version: int = Field(ge=1)
