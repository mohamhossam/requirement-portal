"""GetRequirement use case."""

from __future__ import annotations

from smb_requirement_agent.application.errors import RequirementNotFoundError
from smb_requirement_agent.application.ports.requirement_repository import RequirementRepositoryPort
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class GetRequirement:
    """Retrieves an existing Requirement by its identifier.

    Raises RequirementNotFoundError when no Requirement with the given ID exists,
    allowing callers to map this to an appropriate client error (e.g. HTTP 404).
    """

    def __init__(self, repository: RequirementRepositoryPort) -> None:
        self._repository = repository

    def execute(self, requirement_id: RequirementId) -> Requirement:
        requirement = self._repository.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        return requirement
