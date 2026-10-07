"""In-memory analysis audit persistence."""

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.domain.analysis.entities import AnalysisRound, ClarificationQuestion
from smb_requirement_agent.domain.analysis.errors import (
    ClarificationVersionConflictError,
    InvalidClarificationTransitionError,
)
from smb_requirement_agent.domain.analysis.value_objects import AnalysisId, QuestionId
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class InMemoryAnalysisAuditRepository(AnalysisAuditRepositoryPort):
    def __init__(self, source_changed: Callable[[RequirementId], None]) -> None:
        self._source_changed = source_changed
        self._rounds: dict[str, list[AnalysisRound]] = {}
        self._questions: dict[str, ClarificationQuestion] = {}

    def snapshot_state(self) -> Any:
        return deepcopy(
            (
                self._rounds,
                self._questions,
            )
        )

    def restore_state(self, state: Any) -> None:
        (
            self._rounds,
            self._questions,
        ) = deepcopy(state)

    def append_round(self, round_: AnalysisRound) -> None:
        rounds = self._rounds.setdefault(round_.requirement_id.value, [])
        if any(item.id == round_.id for item in rounds):
            raise PersistenceError(f"Analysis round {round_.id.value!r} already exists.")
        if round_.number != len(rounds) + 1:
            raise PersistenceError("Analysis round numbers must be contiguous.")
        rounds.append(round_)
        self._source_changed(round_.requirement_id)

    def list_rounds(self, requirement_id: RequirementId) -> list[AnalysisRound]:
        return list(self._rounds.get(requirement_id.value, []))

    def get_round(
        self, requirement_id: RequirementId, analysis_id: AnalysisId
    ) -> AnalysisRound | None:
        return next(
            (item for item in self._rounds.get(requirement_id.value, []) if item.id == analysis_id),
            None,
        )

    def add_question(self, question: ClarificationQuestion) -> None:
        if question.id.value in self._questions:
            raise PersistenceError(f"Question {question.id.value!r} already exists.")
        self._questions[question.id.value] = question
        self._source_changed(question.requirement_id)

    def save_question(self, question: ClarificationQuestion) -> None:
        current = self._questions.get(question.id.value)
        if current is None:
            raise PersistenceError(f"Question {question.id.value!r} does not exist.")
        if not current.is_active:
            raise InvalidClarificationTransitionError(
                "Resolved or superseded questions cannot be changed."
            )
        if question.version != current.version + 1:
            raise ClarificationVersionConflictError(
                "Question changed since it was loaded. Refresh and try again."
            )
        self._questions[question.id.value] = question
        self._source_changed(question.requirement_id)

    def get_question(
        self, requirement_id: RequirementId, question_id: QuestionId
    ) -> ClarificationQuestion | None:
        question = self._questions.get(question_id.value)
        if question is None or question.requirement_id != requirement_id:
            return None
        return question

    def list_questions(self, requirement_id: RequirementId) -> list[ClarificationQuestion]:
        return [item for item in self._questions.values() if item.requirement_id == requirement_id]
