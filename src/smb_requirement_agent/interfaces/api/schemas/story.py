"""HTTP schemas for User Story review."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from smb_requirement_agent.breakdown.domain.story.entities import StoryChangeOperation
from smb_requirement_agent.breakdown.domain.story.quality import (
    FindingSource,
    InvestCriterion,
    SpidrPattern,
    StoryQualityStatus,
)
from smb_requirement_agent.interfaces.api.schemas.architecture import ArchitectureImpactResponse
from smb_requirement_agent.interfaces.api.schemas.bounds import (
    MAX_IDENTIFIER_CHARACTERS,
    MAX_ITEMS,
    Identifier,
    Name,
    Text,
)
from smb_requirement_agent.interfaces.api.schemas.epic import ProvenanceResponse, StalenessResponse
from smb_requirement_agent.interfaces.api.schemas.generation import ActionAvailabilityResponse
from smb_requirement_agent.interfaces.api.schemas.governance import ApprovalResponse
from smb_requirement_agent.shared_kernel.generation import GenerationStatus


class AcceptanceCriterionPayload(BaseModel):
    given: Text
    when: Text
    then: Text


class StoryContentRequest(BaseModel):
    role: Name
    action: Text
    value: Text
    acceptance_criteria: list[AcceptanceCriterionPayload] = Field(
        min_length=1, max_length=MAX_ITEMS
    )
    source_reconciled: bool = False


class StoryDraftRequest(StoryContentRequest):
    expected_version: int


class SplitStoryRequest(BaseModel):
    replacements: list[StoryContentRequest] = Field(min_length=2, max_length=MAX_ITEMS)
    expected_set_version: int = Field(ge=1)


class MergeStoriesRequest(BaseModel):
    story_ids: list[Identifier] = Field(min_length=2, max_length=MAX_ITEMS)
    replacement: StoryContentRequest
    expected_set_version: int = Field(ge=1)


class StoryActionsResponse(BaseModel):
    approve: ActionAvailabilityResponse
    regenerate: ActionAvailabilityResponse
    model_config = ConfigDict(frozen=True)


class StoryResponse(BaseModel):
    id: str
    version: int
    feature_id: str
    role: str
    action: str
    value: str
    voice: str
    acceptance_criteria: list[AcceptanceCriterionPayload]
    status: GenerationStatus
    provenance: ProvenanceResponse
    stale: StalenessResponse | None
    architecture: ArchitectureImpactResponse | None
    content_fingerprint: str
    current_approval: ApprovalResponse | None
    approval_history: list[ApprovalResponse]
    actions: StoryActionsResponse
    story_context_token: str | None = None
    model_config = ConfigDict(frozen=True)


class StorySetResponse(BaseModel):
    feature_id: str
    stories: list[StoryResponse]
    set_version: int
    generation_context_token: str
    model_config = ConfigDict(frozen=True)


class StoryChangeProposalRequest(BaseModel):
    operation: StoryChangeOperation
    source_story_ids: list[Identifier] = Field(min_length=1, max_length=MAX_ITEMS)
    context_token: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)


class StoryProposalCandidateResponse(BaseModel):
    quality: StoryQualityResponse | None = None
    architecture: ArchitectureImpactResponse | None = None
    role: str
    action: str
    value: str
    voice: str
    acceptance_criteria: list[AcceptanceCriterionPayload]
    provenance: ProvenanceResponse


class StoryChangeProposalResponse(BaseModel):
    id: str
    version: int
    feature_id: str
    operation: StoryChangeOperation
    source_story_ids: list[str]
    candidates: list[StoryProposalCandidateResponse]
    model_config = ConfigDict(frozen=True)


class StoryProposalMutationRequest(BaseModel):
    expected_version: int = Field(ge=1)
    expected_set_version: int = Field(ge=1)


class ValidationFindingResponse(BaseModel):
    criterion: InvestCriterion
    passed: bool
    message: str
    source: FindingSource


class SpidrRecommendationResponse(BaseModel):
    pattern: SpidrPattern
    reason: str


class StoryQualityResponse(BaseModel):
    story_id: str
    status: StoryQualityStatus
    failure_count: int
    findings: list[ValidationFindingResponse]
    recommendations: list[SpidrRecommendationResponse]
    provenance: ProvenanceResponse


class FeatureStoryQualityResponse(BaseModel):
    feature_id: str
    stories: list[StoryQualityResponse]


class FeatureStoryQualitySnapshotResponse(FeatureStoryQualityResponse):
    source_fingerprint: str
    generated_at: datetime
    fresh: bool
