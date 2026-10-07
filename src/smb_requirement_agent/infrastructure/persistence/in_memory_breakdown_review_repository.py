"""In-memory breakdown review persistence."""

from copy import deepcopy
from typing import Any

from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.application.ports.breakdown_review_repository import (
    BreakdownReviewRepositoryPort,
)
from smb_requirement_agent.domain.review.entities import BreakdownReview
from smb_requirement_agent.domain.shared.identifiers import RequirementId


class InMemoryBreakdownReviewRepository(BreakdownReviewRepositoryPort):
    def __init__(self) -> None:
        self._store: dict[str, BreakdownReview] = {}

    def snapshot_state(self) -> Any:
        return deepcopy((self._store,))

    def restore_state(self, state: Any) -> None:
        (self._store,) = deepcopy(state)

    def get(self, requirement_id: RequirementId) -> BreakdownReview | None:
        return self._store.get(requirement_id.value)

    def save(self, review: BreakdownReview) -> None:
        current = self._store.get(review.requirement_id.value)
        if current is not None and current != review and current.version + 1 != review.version:
            raise ArtifactVersionConflictError(
                "Breakdown review changed before this mutation could be saved. Reload it."
            )
        self._store[review.requirement_id.value] = review
