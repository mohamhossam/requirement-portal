"""Backward-compatible batch clarification command."""

from dataclasses import dataclass

from smb_requirement_agent.application.use_cases.analysis_collaboration import (
    AnalysisCollaboration,
    AnalysisWorkspace,
)
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.analysis.errors import InvalidClarificationError
from smb_requirement_agent.domain.analysis.value_objects import ClarificationKind
from smb_requirement_agent.domain.shared.actors import ActorProfile
from smb_requirement_agent.domain.shared.identifiers import RequirementId


@dataclass(frozen=True)
class ClarificationAnswerInput:
    kind: ClarificationKind
    subject: str
    answer: str


class ClarifyRequirementAnalysis:
    def __init__(self, collaboration: AnalysisCollaboration) -> None:
        self._collaboration = collaboration

    def execute(
        self,
        requirement_id: RequirementId,
        answers: tuple[ClarificationAnswerInput, ...],
        expected_analysis_version: int,
        actor: ActorProfile,
    ) -> RequirementAnalysis:
        return self.execute_workspace(
            requirement_id, answers, expected_analysis_version, actor
        ).analysis

    def execute_workspace(
        self,
        requirement_id: RequirementId,
        answers: tuple[ClarificationAnswerInput, ...],
        expected_analysis_version: int,
        actor: ActorProfile,
    ) -> AnalysisWorkspace:
        if not answers:
            raise InvalidClarificationError("At least one clarification answer is required.")
        keys = [(item.kind, item.subject.strip().casefold()) for item in answers]
        if len(keys) != len(set(keys)):
            raise InvalidClarificationError(
                "Each uncertainty can be answered only once per request."
            )
        return self._collaboration.resolve_legacy_batch(
            requirement_id,
            tuple((item.kind, item.subject, item.answer) for item in answers),
            expected_analysis_version,
            actor,
        )
