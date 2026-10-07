"""Governance's reaction to changed breakdown evidence (ADR-0021, ADR-0103 §3).

A review that was submitted or approved attests to content that has now changed, so it returns
to `needs_revision`. A review that was never submitted is left as it is.
"""

from smb_requirement_agent.application.ports.breakdown_review_repository import (
    BreakdownReviewRepositoryPort,
)
from smb_requirement_agent.shared_kernel.events import DomainEvent


class ResetApprovalWorkflow:
    """Handler for every event that changes what a breakdown review attests to."""

    def __init__(self, reviews: BreakdownReviewRepositoryPort) -> None:
        self._reviews = reviews

    def on_change(self, event: DomainEvent) -> None:
        review = self._reviews.get(event.requirement_id)
        if review is None:
            return
        updated = review.request_revision()
        if updated is not review:
            self._reviews.save(updated)
