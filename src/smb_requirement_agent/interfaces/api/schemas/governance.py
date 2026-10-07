"""HTTP contracts for Slice 9 approval governance."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from smb_requirement_agent.domain.review.entities import BreakdownStatus
from smb_requirement_agent.domain.shared.actors import ActorSnapshot
from smb_requirement_agent.domain.shared.approval import (
    Approval,
    ApprovalDecision,
    ApprovalTarget,
    ApprovalTargetKind,
    ReviewComment,
)
from smb_requirement_agent.domain.shared.generation import GenerationStatus
from smb_requirement_agent.interfaces.api.schemas.bounds import (
    MAX_IDENTIFIER_CHARACTERS,
    RequiredText,
    Text,
)
from smb_requirement_agent.interfaces.api.schemas.identity import ActorResponse


def _actor(actor: ActorSnapshot) -> ActorResponse:
    return ActorResponse(
        id=actor.id.value,
        display_name=actor.display_name,
        email=actor.email,
    )


class ApprovalTargetResponse(BaseModel):
    kind: ApprovalTargetKind
    item_id: str

    @classmethod
    def from_domain(cls, value: ApprovalTarget) -> ApprovalTargetResponse:
        return cls(kind=value.kind, item_id=value.item_id)


class ApprovalResponse(BaseModel):
    id: str
    target: ApprovalTargetResponse
    decision: ApprovalDecision
    subject_fingerprint: str
    recorded_by: ActorResponse
    recorded_at: datetime
    rationale: str | None

    @classmethod
    def from_domain(cls, value: Approval) -> ApprovalResponse:
        return cls(
            id=value.id.value,
            target=ApprovalTargetResponse.from_domain(value.target),
            decision=value.decision,
            subject_fingerprint=value.subject_fingerprint,
            recorded_by=_actor(value.recorded_by),
            recorded_at=value.recorded_at,
            rationale=value.rationale,
        )


class ReviewCommentResponse(BaseModel):
    id: str
    target: ApprovalTargetResponse
    body: str
    recorded_by: ActorResponse
    recorded_at: datetime

    @classmethod
    def from_domain(cls, value: ReviewComment) -> ReviewCommentResponse:
        return cls(
            id=value.id,
            target=ApprovalTargetResponse.from_domain(value.target),
            body=value.body,
            recorded_by=_actor(value.recorded_by),
            recorded_at=value.recorded_at,
        )


class ApprovalRequest(BaseModel):
    expected_version: int = Field(ge=1)
    expected_content_fingerprint: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    rationale: Text | None = None


class FingerprintRequest(BaseModel):
    expected_fingerprint: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    expected_version: int = Field(ge=1)
    rationale: Text | None = None


class StoryRejectionRequest(BaseModel):
    reason: RequiredText
    expected_fingerprint: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    expected_version: int = Field(ge=1)
    expected_review_version: int = Field(ge=1)


class ReviewCommentRequest(BaseModel):
    target_kind: ApprovalTargetKind
    target_id: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    body: RequiredText
    expected_version: int = Field(ge=1)


class ApprovalCompletionResponse(BaseModel):
    epic_approved: int
    epic_total: int
    features_approved: int
    features_total: int
    stories_approved: int
    stories_total: int


class ArtifactApprovalResponse(BaseModel):
    target: ApprovalTargetResponse
    parent_id: str | None
    label: str
    status: GenerationStatus
    fingerprint: str
    version: int
    current_approval: ApprovalResponse | None
    approval_history: list[ApprovalResponse]


class ApprovalWorkflowResponse(BaseModel):
    requirement_id: str
    review_version: int
    status: BreakdownStatus
    subject_fingerprint: str | None
    submitted_fingerprint: str | None
    artifacts: list[ArtifactApprovalResponse]
    completion: ApprovalCompletionResponse
    readiness_reasons: list[str]
    blocking_reasons: list[str]
    can_submit: bool
    can_approve_breakdown: bool
    can_comment: bool
    breakdown_approvals: list[ApprovalResponse]
    comments: list[ReviewCommentResponse]
    model_config = ConfigDict(frozen=True)
