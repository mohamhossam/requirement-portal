"""Persistence boundary for collaborative clarification and immutable rounds."""

from typing import Protocol

from smb_requirement_agent.domain.analysis.entities import AnalysisRound, ClarificationQuestion
from smb_requirement_agent.domain.analysis.value_objects import AnalysisId, QuestionId
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class AnalysisAuditRepositoryPort(Protocol):
    def append_round(self, round_: AnalysisRound) -> None: ...

    def list_rounds(self, requirement_id: RequirementId) -> list[AnalysisRound]: ...

    def get_round(
        self, requirement_id: RequirementId, analysis_id: AnalysisId
    ) -> AnalysisRound | None: ...

    def add_question(self, question: ClarificationQuestion) -> None: ...

    def save_question(self, question: ClarificationQuestion) -> None: ...

    def get_question(
        self, requirement_id: RequirementId, question_id: QuestionId
    ) -> ClarificationQuestion | None: ...

    def list_questions(self, requirement_id: RequirementId) -> list[ClarificationQuestion]: ...
