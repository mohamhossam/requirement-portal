"""Read-model boundary for the cross-aggregate Requirement worklist."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from smb_requirement_agent.analysis.domain.entities import (
    ClarificationQuestion,
    RequirementAnalysis,
)
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.breakdown.domain.feature.entities import Feature
from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.governance.domain.review.entities import BreakdownReview
from smb_requirement_agent.identity.domain.entities import RequirementAccess
from smb_requirement_agent.jobs.domain.entities import AiJobOperation
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class WorkflowStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_ANSWERS = "needs_answers"
    REANALYSING = "reanalysing"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    STALE = "stale"
    KNOWLEDGE_REVIEW = "knowledge_review"
    DUPLICATE = "duplicate"


class WorklistSort(StrEnum):
    UPDATED_DESC = "updated_desc"
    UPDATED_ASC = "updated_asc"
    TITLE_ASC = "title_asc"
    TITLE_DESC = "title_desc"


@dataclass(frozen=True)
class RequirementWorklistSnapshot:
    """Current state needed to classify one Requirement's review journey."""

    requirement: Requirement
    analysis: RequirementAnalysis | None
    epic: Epic | None
    features: tuple[Feature, ...]
    stories: tuple[UserStory, ...]
    updated_at: datetime
    access: RequirementAccess | None = None
    questions: tuple[ClarificationQuestion, ...] = ()
    active_ai_operation: AiJobOperation | None = None
    review: BreakdownReview | None = None


class RequirementWorklistSnapshotPort(Protocol):
    """Loads application-neutral snapshots without exposing persistence details."""

    def list_snapshots(
        self, requirement_ids: tuple[str, ...] | None = None
    ) -> list[RequirementWorklistSnapshot]: ...


class CurrentWorklistProjectionPort(Protocol):
    """Refresh one current-state projection inside the active unit of work."""

    def refresh(self, requirement_id: RequirementId) -> None: ...
