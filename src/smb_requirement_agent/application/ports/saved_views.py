"""Actor-scoped persistence boundary for reusable Requirement worklist views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from smb_requirement_agent.application.errors import InvalidSavedViewError
from smb_requirement_agent.application.ports.requirement_worklist import (
    WorkflowStatus,
    WorklistSort,
)
from smb_requirement_agent.domain.identity.entities import ActorId


def _text(value: str, field: str, maximum: int) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise InvalidSavedViewError(f"Saved view {field} must not be blank.")
    if len(cleaned) > maximum:
        raise InvalidSavedViewError(f"Saved view {field} must be at most {maximum} characters.")
    return cleaned


@dataclass(frozen=True)
class SavedViewCriteria:
    query: str | None = None
    workflow_statuses: tuple[WorkflowStatus, ...] = ()
    sort: WorklistSort = WorklistSort.UPDATED_DESC
    owner_id: ActorId | None = None
    assigned_to_me: bool = False

    def __post_init__(self) -> None:
        query = self.query.strip() if self.query is not None else None
        if query and len(query) > 200:
            raise InvalidSavedViewError("Saved view search must be at most 200 characters.")
        object.__setattr__(self, "query", query or None)
        object.__setattr__(
            self,
            "workflow_statuses",
            tuple(dict.fromkeys(self.workflow_statuses)),
        )


@dataclass(frozen=True)
class SavedRequirementView:
    id: str
    actor_id: ActorId
    name: str
    criteria: SavedViewCriteria
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "id", 100))
        object.__setattr__(self, "name", _text(self.name, "name", 80))
        if self.version < 1:
            raise InvalidSavedViewError("Saved view version must be positive.")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise InvalidSavedViewError("Saved view timestamps must be timezone-aware.")


class SavedViewRepositoryPort(Protocol):
    def list_for_actor(self, actor_id: ActorId) -> list[SavedRequirementView]: ...

    def get(self, view_id: str) -> SavedRequirementView | None: ...

    def add(self, view: SavedRequirementView) -> None: ...

    def save(self, view: SavedRequirementView, expected_version: int) -> None: ...

    def delete(self, view_id: str, expected_version: int) -> None: ...

    def name_exists(
        self, actor_id: ActorId, name: str, *, excluding_id: str | None = None
    ) -> bool: ...
