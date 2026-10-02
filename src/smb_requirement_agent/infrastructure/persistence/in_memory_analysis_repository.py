"""In-memory analysis repository adapter."""

from copy import deepcopy
from typing import Any

from smb_requirement_agent.application.errors import RequirementAnalysisConflictError
from smb_requirement_agent.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.requirement.value_objects import RequirementId


class InMemoryRequirementAnalysisRepository(RequirementAnalysisRepositoryPort):
    """In-memory persistence for requirement analyses."""

    def __init__(self) -> None:
        self._store: dict[str, RequirementAnalysis] = {}

    def snapshot_state(self) -> Any:
        return deepcopy((self._store,))

    def restore_state(self, state: Any) -> None:
        (self._store,) = deepcopy(state)

    def save(self, analysis: RequirementAnalysis) -> None:
        current = self._store.get(analysis.requirement_id.value)
        if current is not None and current != analysis and analysis.version != current.version + 1:
            raise RequirementAnalysisConflictError(
                "Analysis changed before this mutation could be saved. Reload it."
            )
        self._store[analysis.requirement_id.value] = analysis

    def get_by_requirement_id(self, requirement_id: RequirementId) -> RequirementAnalysis | None:
        return self._store.get(requirement_id.value)

    def delete_by_requirement_id(self, requirement_id: RequirementId) -> None:
        if requirement_id.value in self._store:
            del self._store[requirement_id.value]
