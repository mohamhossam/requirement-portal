"""GetEpic use case."""

from __future__ import annotations

from smb_requirement_agent.breakdown.application.errors import EpicNotFoundError
from smb_requirement_agent.breakdown.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.requirements.application.errors import RequirementNotFoundError
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class GetEpic:
    """Retrieves the Epic for a requirement."""

    def __init__(
        self,
        requirement_repository: RequirementRepositoryPort,
        epic_repository: EpicRepositoryPort,
    ) -> None:
        self._requirements = requirement_repository
        self._epics = epic_repository

    def execute(self, requirement_id: RequirementId) -> Epic:
        if self._requirements.get(requirement_id) is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")

        epic = self._epics.get_by_requirement_id(requirement_id)
        if epic is None:
            raise EpicNotFoundError(f"No Epic exists for requirement {requirement_id.value!r}.")
        return epic
