"""How governance answers an analysis question raised as a review flag.

Governance owns this port; the composition root fills it with analysis's
`AnalysisCollaboration` (ADR-0103 Amendment 3), so governance never imports another
context's use case.
"""

from typing import Protocol

from smb_requirement_agent.analysis.domain.entities import (
    ClarificationQuestion,
    RequirementAnalysis,
)
from smb_requirement_agent.analysis.domain.value_objects import QuestionId
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class AnsweredQuestion(Protocol):
    """What governance reads back after an answer: the analysis it changed."""

    @property
    def analysis(self) -> RequirementAnalysis: ...


class OpenQuestionPort(Protocol):
    def question(
        self, requirement_id: RequirementId, question_id: QuestionId
    ) -> ClarificationQuestion: ...

    def resolve(
        self,
        requirement_id: RequirementId,
        question_id: QuestionId,
        answer: str | None,
        expected_version: int,
        actor: ActorProfile,
    ) -> AnsweredQuestion: ...
