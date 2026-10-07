"""The knowledge screen, as analysis sees it (ADR-0103 Amendment 1, F1).

Analysis sits upstream of the screening context, so it asks for answer suggestions, checks the
confirmation gate and records a suggestion's provenance through these ports it owns. The
composition root implements them with the screening context's classes. Analysis asks for a screen
through requirements' `ScreeningRequestPort`.
"""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.domain.analysis.entities import ClarificationQuestion
from smb_requirement_agent.domain.analysis.value_objects import QuestionId
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.lineage import SourceLineage


class AnswerSuggestionRequestPort(Protocol):
    def schedule(
        self,
        requirement_id: RequirementId,
        questions: tuple[ClarificationQuestion, ...],
    ) -> None:
        """Ask for answer suggestions to these open questions."""
        ...


class KnowledgeGatePort(Protocol):
    def require_ready(self, requirement_id: RequirementId) -> None:
        """Raise unless the knowledge screen lets this analysis be confirmed."""
        ...


class SuggestionProvenancePort(Protocol):
    def suggestion_provenance(
        self, requirement_id: RequirementId, question_id: QuestionId, suggestion_id: str
    ) -> tuple[SourceLineage, ...]:
        """The lineage an answer taken from this suggestion records.

        Raises when the suggestion is absent or stale.
        """
        ...
