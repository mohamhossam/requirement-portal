"""Revision history transport schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from smb_requirement_agent.interfaces.api.schemas.identity import ActorResponse


class RequirementRevisionResponse(BaseModel):
    number: int
    created_at: datetime
    title: str
    description: str
    status: str
    model_config = ConfigDict(frozen=True)


class BreakdownRevisionResponse(BaseModel):
    number: int
    created_at: datetime
    has_analysis: bool
    analysis_human_confirmed: bool
    clarification_count: int
    unresolved_count: int
    intent_proposal_count: int
    intent_decision_count: int
    epic_name: str | None
    epic_status: str | None
    feature_count: int
    approved_feature_count: int
    story_count: int
    edited_story_count: int
    stale_story_count: int
    has_review: bool
    review_blocker_count: int
    review_decision_count: int
    review_status: str | None
    approval_count: int
    comment_count: int
    submitted_fingerprint: str | None
    exportable: bool
    final_approved_by: ActorResponse | None
    final_approved_at: datetime | None
    model_config = ConfigDict(frozen=True)


class RevisionHistoryResponse(BaseModel):
    requirement_revisions: list[RequirementRevisionResponse]
    breakdown_revisions: list[BreakdownRevisionResponse]
    model_config = ConfigDict(frozen=True)


class BreakdownComparisonResponse(BaseModel):
    from_revision: int
    to_revision: int
    changes: list[str]
    model_config = ConfigDict(frozen=True)
