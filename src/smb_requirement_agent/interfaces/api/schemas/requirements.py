"""HTTP transport schemas for the Requirements API.

These Pydantic models are interface-layer concerns only.
They are never imported by Domain or Application.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from smb_requirement_agent.application.ports.requirement_worklist import WorkflowStatus
from smb_requirement_agent.application.use_cases.requirement_worklist import (
    NextAction,
    WorkflowStage,
)
from smb_requirement_agent.domain.jobs.entities import AiJobOperation
from smb_requirement_agent.domain.requirement.intake_limits import (
    MAX_CONTEXT_CHARACTERS,
    MAX_DESCRIPTION_CHARACTERS,
    MAX_LIST_ITEM_CHARACTERS,
    MAX_LIST_ITEMS,
    MAX_TITLE_CHARACTERS,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementStatus
from smb_requirement_agent.interfaces.api.schemas.identity import ActorResponse


class LastActivityResponse(BaseModel):
    action: str
    occurred_at: datetime
    actor: ActorResponse | None


# The domain intake limits (domain/requirement/intake_limits.py), repeated here
# so over-long input is a 422 naming the field and appears in the OpenAPI contract.
Title = Annotated[str, Field(max_length=MAX_TITLE_CHARACTERS)]
Description = Annotated[str, Field(max_length=MAX_DESCRIPTION_CHARACTERS)]
ContextText = Annotated[str, Field(max_length=MAX_CONTEXT_CHARACTERS)]
ContextItem = Annotated[str, Field(max_length=MAX_LIST_ITEM_CHARACTERS)]
ContextList = Annotated[list[ContextItem], Field(max_length=MAX_LIST_ITEMS)]


class CreateRequirementRequest(BaseModel):
    title: Title
    description: Description
    desired_outcome: ContextText | None = None
    customer_context: ContextText | None = None
    channels: ContextList = Field(default_factory=list)
    systems: ContextList = Field(default_factory=list)
    business_rules: ContextList = Field(default_factory=list)
    constraints: ContextList = Field(default_factory=list)


class UpdateRequirementRequest(BaseModel):
    title: Title
    description: Description
    desired_outcome: ContextText | None = None
    customer_context: ContextText | None = None
    channels: ContextList | None = None
    systems: ContextList | None = None
    business_rules: ContextList | None = None
    constraints: ContextList | None = None
    expected_version: int = Field(ge=1)
    impact_acknowledged: bool = False


class RequirementDraftRequest(BaseModel):
    title: Title = ""
    description: Description = ""
    desired_outcome: ContextText = ""
    customer_context: ContextText = ""
    channels: ContextList = Field(default_factory=list)
    systems: ContextList = Field(default_factory=list)
    business_rules: ContextList = Field(default_factory=list)
    constraints: ContextList = Field(default_factory=list)


class SaveRequirementDraftRequest(RequirementDraftRequest):
    expected_version: int


class PromoteRequirementDraftRequest(BaseModel):
    expected_version: int


class AnalysisEligibilityResponse(BaseModel):
    eligible: bool
    missing_fields: list[str]


class RequirementResponse(BaseModel):
    id: str
    title: str
    description: str
    status: RequirementStatus
    duplicate_of_requirement_id: str | None = None
    desired_outcome: str | None
    customer_context: str | None
    channels: list[str]
    systems: list[str]
    business_rules: list[str]
    constraints: list[str]
    version: int
    updated_at: datetime | None
    analysis_eligibility: AnalysisEligibilityResponse
    analysis_context_token: str | None = None


class RequirementDraftResponse(BaseModel):
    id: str
    title: str
    description: str
    desired_outcome: str
    customer_context: str
    channels: list[str]
    systems: list[str]
    business_rules: list[str]
    constraints: list[str]
    version: int
    updated_at: datetime
    analysis_eligibility: AnalysisEligibilityResponse


class RequirementImpactResponse(BaseModel):
    requirement_id: str
    requirement_version: int
    analysis_count: int
    epic_count: int
    feature_count: int
    story_count: int
    source_changed: bool
    requires_acknowledgement: bool


class ArtifactCountsResponse(BaseModel):
    epics: int
    features: int
    stories: int


class RequirementWorklistItemResponse(RequirementResponse):
    workflow_status: WorkflowStatus
    current_stage: WorkflowStage
    next_action: NextAction
    answered_items: int
    unresolved_items: int
    stale_items: int
    artifact_counts: ArtifactCountsResponse
    updated_at: datetime
    owner: ActorResponse | None
    reviewer_count: int
    active_ai_operation: AiJobOperation | None
    last_activity: LastActivityResponse | None


class OwnerFacetResponse(BaseModel):
    actor: ActorResponse
    count: int


class WorkflowStatusCountsResponse(BaseModel):
    draft: int
    needs_answers: int
    reanalysing: int
    ready_for_review: int
    approved: int
    needs_revision: int
    stale: int
    knowledge_review: int
    duplicate: int


class RequirementListResponse(BaseModel):
    requirements: list[RequirementWorklistItemResponse]
    attention: list[RequirementWorklistItemResponse]
    total: int
    offset: int
    limit: int
    has_more: bool
    status_counts: WorkflowStatusCountsResponse
    owner_facets: list[OwnerFacetResponse]
