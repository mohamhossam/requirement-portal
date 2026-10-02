"""Invalidate submitted governance when its evidence changes."""

from smb_requirement_agent.application.ports.breakdown_review_repository import (
    BreakdownReviewRepositoryPort,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementId


class InvalidateApprovalWorkflow:
    """Persist the review lifecycle consequence of a source/evidence mutation."""

    def __init__(self, reviews: BreakdownReviewRepositoryPort) -> None:
        self._reviews = reviews

    def execute(self, requirement_id: RequirementId) -> None:
        review = self._reviews.get(requirement_id)
        if review is None:
            return
        updated = review.request_revision()
        if updated is not review:
            self._reviews.save(updated)
