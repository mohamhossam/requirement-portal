"""In-memory adapter for RequirementRepositoryPort.

Intended for development and testing only.  A single shared instance must be
used across all requests within a process to preserve state between HTTP calls.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from smb_requirement_agent.application.errors import (
    DuplicateRequirementError,
    RequirementVersionConflictError,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class InMemoryRequirementRepository(RequirementRepositoryPort):
    """Stores Requirements in a plain dictionary.

    The internal dictionary is not exposed to callers; only the port
    operations are public.
    """

    def __init__(self) -> None:
        self._store: dict[str, Requirement] = {}

    def snapshot_state(self) -> Any:
        return deepcopy((self._store,))

    def restore_state(self, state: Any) -> None:
        (self._store,) = deepcopy(state)

    def add(self, requirement: Requirement) -> None:
        if requirement.id.value in self._store:
            raise DuplicateRequirementError(f"Requirement {requirement.id.value!r} already exists.")
        self._store[requirement.id.value] = requirement

    def get(self, requirement_id: RequirementId) -> Requirement | None:
        return self._store.get(requirement_id.value)

    def list_all(self) -> list[Requirement]:
        # Newest first, approximating the persistent adapter's updated_at order
        # from insertion order (a re-save keeps a dict key in place).
        return list(reversed(self._store.values()))

    def save(self, requirement: Requirement) -> None:
        current = self._store.get(requirement.id.value)
        if (
            current is not None
            and requirement.version.value > 1
            and current.version.value != requirement.version.value - 1
        ):
            raise RequirementVersionConflictError(
                f"Requirement {requirement.id.value!r} changed before it could be saved."
            )
        self._store[requirement.id.value] = requirement
