"""Read boundaries for traceable portfolio activity and reporting evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from smb_requirement_agent.domain.identity.entities import ActorId, ActorSnapshot
from smb_requirement_agent.domain.requirement.value_objects import RequirementId


class ActivityCategory(StrEnum):
    REQUIREMENT = "requirement"
    CLARIFICATION = "clarification"
    ACCESS = "access"
    GENERATION = "generation"
    GOVERNANCE = "governance"
    KNOWLEDGE = "knowledge"


class ActivityAction(StrEnum):
    REQUIREMENT_CREATED = "requirement_created"
    REQUIREMENT_UPDATED = "requirement_updated"
    ANALYSIS_GENERATED = "analysis_generated"
    ANALYSIS_CONFIRMED = "analysis_confirmed"
    INTENT_PROPOSAL_DECIDED = "intent_proposal_decided"
    QUESTION_ASKED = "question_asked"
    QUESTION_ASSIGNED = "question_assigned"
    QUESTION_CLASSIFIED = "question_classified"
    QUESTION_RESOLVED = "question_resolved"
    QUESTION_SUPERSEDED = "question_superseded"
    OWNER_CLAIMED = "owner_claimed"
    OWNER_TRANSFERRED = "owner_transferred"
    REVIEWER_ASSIGNED = "reviewer_assigned"
    REVIEWER_REMOVED = "reviewer_removed"
    AI_SUCCEEDED = "ai_succeeded"
    AI_FAILED = "ai_failed"
    AI_CANCELLED = "ai_cancelled"
    ARTIFACT_APPROVED = "artifact_approved"
    STORY_REJECTED = "story_rejected"
    REVIEW_FLAG_RESOLVED = "review_flag_resolved"
    REVIEW_COMMENTED = "review_commented"
    BREAKDOWN_SUBMITTED = "breakdown_submitted"
    BREAKDOWN_NEEDS_REVISION = "breakdown_needs_revision"
    BREAKDOWN_APPROVED = "breakdown_approved"
    KNOWLEDGE_SCREENED = "knowledge_screened"
    REQUIREMENT_MARKED_DISTINCT = "requirement_marked_distinct"
    REQUIREMENT_MARKED_DUPLICATE = "requirement_marked_duplicate"
    CONFLICT_RESOLUTION_PROPOSED = "conflict_resolution_proposed"
    CONFLICT_RESOLUTION_ACCEPTED = "conflict_resolution_accepted"
    CONFLICT_RESOLVED = "conflict_resolved"
    FINDING_SOURCE_RETIRED = "finding_source_retired"


class AuditSourceKind(StrEnum):
    REQUIREMENT_REVISION = "requirement_revision"
    BREAKDOWN_REVISION = "breakdown_revision"
    ANALYSIS_ROUND = "analysis_round"
    CLARIFICATION_QUESTION = "clarification_question"
    INTENT_PROPOSAL = "intent_proposal"
    ACCESS_CHANGE = "access_change"
    AI_JOB = "ai_job"
    APPROVAL = "approval"
    REVIEW_COMMENT = "review_comment"
    REVIEW_DECISION = "review_decision"
    REVIEW_FLAG = "review_flag"
    KNOWLEDGE_FINDING = "knowledge_finding"


@dataclass(frozen=True)
class AuditSourceReference:
    kind: AuditSourceKind
    source_id: str


@dataclass(frozen=True)
class ActivityEvent:
    id: str
    requirement_id: RequirementId
    requirement_title: str
    category: ActivityCategory
    action: ActivityAction
    summary: str
    occurred_at: datetime
    actor: ActorSnapshot | None
    target_id: str | None
    resource_path: str
    sources: tuple[AuditSourceReference, ...]


@dataclass(frozen=True)
class BlockerEvidence:
    id: str
    requirement_id: RequirementId
    requirement_title: str
    title: str
    opened_at: datetime
    actor: ActorSnapshot | None
    resource_path: str
    source: AuditSourceReference


class ActivityReadPort(Protocol):
    def query(self, query: ActivityQuery) -> ActivityResult: ...

    def window_events(self, start: datetime, before: datetime) -> list[ActivityEvent]: ...

    def aggregate_report(self, start: datetime, before: datetime) -> ActivityReportEvidence: ...

    def list_events(self) -> list[ActivityEvent]: ...

    def list_events_for_requirement(self, requirement_id: RequirementId) -> list[ActivityEvent]: ...


class ReportingReadPort(Protocol):
    def list_current_blockers(self) -> list[BlockerEvidence]: ...


@dataclass(frozen=True)
class ActivityQuery:
    requirement_id: RequirementId | None = None
    categories: frozenset[ActivityCategory] = frozenset()
    actions: frozenset[ActivityAction] = frozenset()
    actor_id: ActorId | None = None
    occurred_from: datetime | None = None
    occurred_before: datetime | None = None
    offset: int = 0
    limit: int = 25


@dataclass(frozen=True)
class ActivityResult:
    items: tuple[ActivityEvent, ...]
    total: int
    offset: int
    limit: int
    has_more: bool


@dataclass(frozen=True)
class WeeklyActivityEvidence:
    week_start: datetime
    action: ActivityAction
    event_ids: tuple[str, ...]


@dataclass(frozen=True)
class ActivityReportEvidence:
    weekly: tuple[WeeklyActivityEvidence, ...]
    opened_ids: tuple[str, ...]
    resolved_ids: tuple[str, ...]
    median_resolution_hours: float | None
