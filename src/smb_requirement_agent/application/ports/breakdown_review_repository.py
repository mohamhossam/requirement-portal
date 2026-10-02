"""Persistence boundary for current breakdown review state."""

from typing import Protocol

from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.domain.review.entities import BreakdownReview


class BreakdownReviewRepositoryPort(Protocol):
    def get(self, requirement_id: RequirementId) -> BreakdownReview | None: ...

    def save(self, review: BreakdownReview) -> None: ...
