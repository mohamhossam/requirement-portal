"""Offline in-memory adapter for resumable Requirement drafts."""

from copy import deepcopy
from typing import Any

from smb_requirement_agent.application.errors import RequirementVersionConflictError
from smb_requirement_agent.application.ports.requirement_draft_repository import (
    RequirementDraftRepositoryPort,
)
from smb_requirement_agent.domain.requirement.entities import RequirementDraft
from smb_requirement_agent.domain.requirement.value_objects import RequirementId


class InMemoryRequirementDraftRepository(RequirementDraftRepositoryPort):
    def __init__(self) -> None:
        self._drafts: dict[str, RequirementDraft] = {}

    def snapshot_state(self) -> Any:
        return deepcopy((self._drafts,))

    def restore_state(self, state: Any) -> None:
        (self._drafts,) = deepcopy(state)

    def add(self, draft: RequirementDraft) -> None:
        self._drafts[draft.id.value] = draft

    def get(self, draft_id: RequirementId) -> RequirementDraft | None:
        return self._drafts.get(draft_id.value)

    def list_all(self) -> list[RequirementDraft]:
        return sorted(self._drafts.values(), key=lambda item: item.updated_at, reverse=True)

    def save(self, draft: RequirementDraft) -> None:
        current = self._drafts.get(draft.id.value)
        if current is None or current.version.value != draft.version.value - 1:
            raise RequirementVersionConflictError(
                f"Requirement draft {draft.id.value!r} changed before it could be saved."
            )
        self._drafts[draft.id.value] = draft

    def delete(self, draft_id: RequirementId) -> None:
        self._drafts.pop(draft_id.value, None)
