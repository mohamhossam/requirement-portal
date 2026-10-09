"""In-memory Epic repository adapter."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.breakdown.domain.epic.value_objects import EpicId
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class InMemoryEpicRepository:
    """Stores Epics in a plain dictionary, keyed by requirement ID."""

    def __init__(self) -> None:
        self._store: dict[str, Epic] = {}

    def snapshot_state(self) -> Any:
        return deepcopy((self._store,))

    def restore_state(self, state: Any) -> None:
        (self._store,) = deepcopy(state)

    def save(self, epic: Epic) -> None:
        current = self._store.get(epic.requirement_id.value)
        if current is not None and current != epic and epic.version != current.version + 1:
            raise ArtifactVersionConflictError(
                "The Epic changed before this mutation could be saved. Reload it."
            )
        self._store[epic.requirement_id.value] = epic

    def get_by_requirement_id(self, requirement_id: RequirementId) -> Epic | None:
        return self._store.get(requirement_id.value)

    def delete_by_requirement_id(self, requirement_id: RequirementId) -> None:
        self._store.pop(requirement_id.value, None)

    def requirement_id_for_epic(self, epic_id: EpicId) -> RequirementId | None:
        """Resolve ownership for the in-memory revision-tracking decorator."""
        epic = next((item for item in self._store.values() if item.id == epic_id), None)
        return epic.requirement_id if epic is not None else None
