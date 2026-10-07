"""Create explicit immutable requirement-analysis rounds."""

from smb_requirement_agent.application.use_cases.analysis_collaboration import (
    AnalysisCollaboration,
    AnalysisWorkspace,
)
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class AnalyzeRequirement:
    def __init__(self, collaboration: AnalysisCollaboration) -> None:
        self._collaboration = collaboration

    def execute(
        self, actor: ActorProfile, requirement_id: RequirementId, *, force: bool = False
    ) -> RequirementAnalysis:
        return self.execute_workspace(actor, requirement_id, force=force).analysis

    def execute_workspace(
        self, actor: ActorProfile, requirement_id: RequirementId, *, force: bool = False
    ) -> AnalysisWorkspace:
        return self._collaboration.generate(actor, requirement_id, force=force)
