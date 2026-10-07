"""Immutable snapshots used for requirement traceability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.identity.entities import RequirementAccess
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.review.entities import BreakdownReview
from smb_requirement_agent.domain.revision.errors import InvalidRevisionError
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.staleness import require_aware


@dataclass(frozen=True, order=True)
class RevisionNumber:
    """A positive, requirement-local revision sequence number."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 1:
            raise InvalidRevisionError("Revision number must be greater than zero.")


@dataclass(frozen=True)
class RequirementRevision:
    """An immutable snapshot of human-authored requirement input."""

    requirement_id: RequirementId
    number: RevisionNumber
    created_at: datetime
    requirement: Requirement
    access: RequirementAccess | None = None

    def __post_init__(self) -> None:
        require_aware(self.created_at, "revision created_at")
        if self.requirement.id != self.requirement_id:
            raise InvalidRevisionError("Requirement revision snapshot has a different ID.")
        if self.access is not None and self.access.requirement_id != self.requirement_id:
            raise InvalidRevisionError("Requirement revision access has a different ID.")


@dataclass(frozen=True)
class BreakdownRevision:
    """An immutable snapshot of the current generated and human-reviewed breakdown."""

    requirement_id: RequirementId
    number: RevisionNumber
    created_at: datetime
    analysis: RequirementAnalysis | None
    epic: Epic | None
    features: tuple[Feature, ...]
    stories: tuple[UserStory, ...] = ()
    review: BreakdownReview | None = None

    def __post_init__(self) -> None:
        require_aware(self.created_at, "revision created_at")
        if self.analysis is not None and self.analysis.requirement_id != self.requirement_id:
            raise InvalidRevisionError("Analysis snapshot belongs to a different requirement.")
        if self.epic is not None and self.epic.requirement_id != self.requirement_id:
            raise InvalidRevisionError("Epic snapshot belongs to a different requirement.")
        if self.epic is None and self.features:
            raise InvalidRevisionError("Feature snapshots require an Epic snapshot.")
        if self.epic is not None and any(item.epic_id != self.epic.id for item in self.features):
            raise InvalidRevisionError("A Feature snapshot belongs to a different Epic.")
        feature_ids = {item.id for item in self.features}
        if any(item.feature_id not in feature_ids for item in self.stories):
            raise InvalidRevisionError("A Story snapshot belongs to a different Feature tree.")
        if self.review is not None and self.review.requirement_id != self.requirement_id:
            raise InvalidRevisionError("Review snapshot belongs to a different requirement.")
