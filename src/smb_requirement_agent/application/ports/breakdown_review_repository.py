"""Persistence boundary for current breakdown review state."""

from typing import Protocol

from smb_requirement_agent.domain.review.entities import BreakdownReview
from smb_requirement_agent.domain.shared.identifiers import RequirementId


class BreakdownReviewRepositoryPort(Protocol):
    def get(self, requirement_id: RequirementId) -> BreakdownReview | None: ...

    def save(self, review: BreakdownReview) -> None: ...
