"""Transport schemas for Slice 10A activity, saved views, and reports."""

from datetime import datetime

from pydantic import BaseModel, Field

from smb_requirement_agent.application.ports.activity import (
    ActivityAction,
    ActivityCategory,
    AuditSourceKind,
)
from smb_requirement_agent.application.ports.requirement_worklist import (
    WorkflowStatus,
    WorklistSort,
)
from smb_requirement_agent.interfaces.api.schemas.bounds import (
    MAX_ITEMS,
    Identifier,
)
from smb_requirement_agent.interfaces.api.schemas.identity import ActorResponse


class AuditSourceResponse(BaseModel):
    kind: AuditSourceKind
    source_id: str


class ActivityEventResponse(BaseModel):
    id: str
    requirement_id: str
    requirement_title: str
    category: ActivityCategory
    action: ActivityAction
    summary: str
    occurred_at: datetime
    actor: ActorResponse | None
    target_id: str | None
    resource_path: str
    sources: list[AuditSourceResponse]


class ActivityListResponse(BaseModel):
    items: list[ActivityEventResponse]
    total: int
    offset: int
    limit: int
    has_more: bool


class SavedViewCriteriaRequest(BaseModel):
    query: str | None = Field(default=None, max_length=200)
    workflow_statuses: list[WorkflowStatus] = Field(default_factory=list, max_length=MAX_ITEMS)
    sort: WorklistSort = WorklistSort.UPDATED_DESC
    owner_id: Identifier | None = None
    assigned_to_me: bool = False


class SavedViewCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    criteria: SavedViewCriteriaRequest


class SavedViewUpdateRequest(SavedViewCreateRequest):
    expected_version: int = Field(ge=1)


class SavedViewResponse(BaseModel):
    id: str
    name: str
    criteria: SavedViewCriteriaRequest
    version: int
    created_at: datetime
    updated_at: datetime


class MetricCountResponse(BaseModel):
    value: int
    evidence_event_ids: list[str]


class WeeklyMetricsResponse(BaseModel):
    week_start: datetime
    week_end: datetime
    requirements_created: MetricCountResponse
    analysis_rounds: MetricCountResponse
    clarifications_resolved: MetricCountResponse
    artifact_approvals: MetricCountResponse
    breakdown_approvals: MetricCountResponse


class ClarificationMetricsResponse(BaseModel):
    opened: MetricCountResponse
    resolved: MetricCountResponse
    resolution_percentage: float
    median_resolution_hours: float | None


class BlockerResponse(BaseModel):
    id: str
    requirement_id: str
    requirement_title: str
    title: str
    opened_at: datetime
    actor: ActorResponse | None
    resource_path: str
    source: AuditSourceResponse


class OperationalReportResponse(BaseModel):
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    weeks: int
    weekly: list[WeeklyMetricsResponse]
    clarification: ClarificationMetricsResponse
    oldest_blockers: list[BlockerResponse]
