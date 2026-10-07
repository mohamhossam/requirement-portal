"""GetRequirementAnalysis use case."""

from smb_requirement_agent.application.errors import (
    RequirementAnalysisNotFoundError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_repository import RequirementRepositoryPort
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.shared.identifiers import RequirementId


class GetRequirementAnalysis:
    """Use case to retrieve the analysis for a given requirement."""

    def __init__(
        self,
        requirement_repository: RequirementRepositoryPort,
        analysis_repository: RequirementAnalysisRepositoryPort,
    ) -> None:
        self._requirement_repo = requirement_repository
        self._analysis_repo = analysis_repository

    def execute(self, requirement_id: RequirementId) -> RequirementAnalysis:
        # First ensure requirement exists
        requirement = self._requirement_repo.get(requirement_id)
        if not requirement:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value} not found.")

        # Then get analysis
        analysis = self._analysis_repo.get_by_requirement_id(requirement_id)
        if not analysis:
            raise RequirementAnalysisNotFoundError(
                f"Analysis for requirement {requirement_id.value} not found."
            )

        return analysis
