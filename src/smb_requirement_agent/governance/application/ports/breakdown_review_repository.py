"""Persistence boundary for current breakdown review state."""

from typing import Protocol

from smb_requirement_agent.governance.domain.review.entities import BreakdownReview
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class BreakdownReviewRepositoryPort(Protocol):
    def get(self, requirement_id: RequirementId) -> BreakdownReview | None: ...

    def save(self, review: BreakdownReview) -> None: ...
