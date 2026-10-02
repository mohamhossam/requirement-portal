"""Requirement analysis repository port."""

from typing import Protocol

from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.requirement.value_objects import RequirementId


class RequirementAnalysisRepositoryPort(Protocol):
    """Outbound port for persisting requirement analyses."""

    def save(self, analysis: RequirementAnalysis) -> None:
        """Save a new or updated requirement analysis."""
        ...

    def get_by_requirement_id(self, requirement_id: RequirementId) -> RequirementAnalysis | None:
        """Retrieve a requirement analysis by its requirement ID."""
        ...

    def delete_by_requirement_id(self, requirement_id: RequirementId) -> None:
        """Delete an analysis by its requirement ID (e.g. when requirement is updated)."""
        ...
