"""PostgreSQL repositories for analyses, their rounds and questions (ADR-0103 PR 10)."""

from __future__ import annotations

from psycopg.errors import RaiseException, UniqueViolation
from psycopg.types.json import Jsonb

from smb_requirement_agent.analysis.application.errors import RequirementAnalysisConflictError
from smb_requirement_agent.analysis.domain.entities import (
    AnalysisRound,
    ClarificationQuestion,
    RequirementAnalysis,
)
from smb_requirement_agent.analysis.domain.errors import (
    ClarificationVersionConflictError,
    InvalidClarificationTransitionError,
)
from smb_requirement_agent.analysis.domain.value_objects import AnalysisId, QuestionId
from smb_requirement_agent.analysis.infrastructure.analysis_payloads import (
    analysis_from_payload,
    analysis_round_from_payload,
    analysis_round_to_payload,
    analysis_to_payload,
    clarification_question_from_payload,
    clarification_question_to_payload,
)
from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import (
    _payload,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class PostgresAnalysisRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def save(self, analysis: RequirementAnalysis) -> None:
        with self._store.connection() as connection:
            result = connection.execute(
                """
                INSERT INTO requirement_analyses (requirement_id, payload)
                VALUES (%s, %s)
                ON CONFLICT (requirement_id) DO UPDATE
                SET payload = EXCLUDED.payload, updated_at = now()
                WHERE (requirement_analyses.payload->>'version')::integer =
                          (EXCLUDED.payload->>'version')::integer - 1
                   OR requirement_analyses.payload = EXCLUDED.payload
                """,
                (analysis.requirement_id.value, Jsonb(analysis_to_payload(analysis))),
            )
            if result.rowcount == 0:
                raise RequirementAnalysisConflictError(
                    "Analysis changed before this mutation could be saved. Reload it."
                )
            self._store.mark_requirement_dirty(analysis.requirement_id)

    def get_by_requirement_id(self, requirement_id: RequirementId) -> RequirementAnalysis | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM requirement_analyses WHERE requirement_id = %s",
                (requirement_id.value,),
            ).fetchone()
        return analysis_from_payload(_payload(row[0])) if row is not None else None

    def delete_by_requirement_id(self, requirement_id: RequirementId) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "DELETE FROM requirement_analyses WHERE requirement_id = %s",
                (requirement_id.value,),
            )
            self._store.mark_requirement_dirty(requirement_id)


class PostgresAnalysisAuditRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def append_round(self, round_: AnalysisRound) -> None:
        with self._store.connection() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO analysis_rounds
                        (requirement_id, analysis_id, round_number, payload)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        round_.requirement_id.value,
                        round_.id.value,
                        round_.number,
                        Jsonb(analysis_round_to_payload(round_)),
                    ),
                )
            except UniqueViolation as exc:
                raise PersistenceError("Analysis round identity or number already exists.") from exc
            self._store.mark_requirement_dirty(round_.requirement_id)

    def list_rounds(self, requirement_id: RequirementId) -> list[AnalysisRound]:
        with self._store.connection() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM analysis_rounds
                WHERE requirement_id = %s ORDER BY round_number
                """,
                (requirement_id.value,),
            ).fetchall()
        return [analysis_round_from_payload(_payload(row[0])) for row in rows]

    def get_round(
        self, requirement_id: RequirementId, analysis_id: AnalysisId
    ) -> AnalysisRound | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """
                SELECT payload FROM analysis_rounds
                WHERE requirement_id = %s AND analysis_id = %s
                """,
                (requirement_id.value, analysis_id.value),
            ).fetchone()
        return analysis_round_from_payload(_payload(row[0])) if row is not None else None

    def add_question(self, question: ClarificationQuestion) -> None:
        with self._store.connection() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO analysis_questions
                        (question_id, requirement_id, first_analysis_id, payload)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        question.id.value,
                        question.requirement_id.value,
                        question.first_analysis_id.value,
                        Jsonb(clarification_question_to_payload(question)),
                    ),
                )
            except UniqueViolation as exc:
                raise PersistenceError(f"Question {question.id.value!r} already exists.") from exc
            self._store.mark_requirement_dirty(question.requirement_id)

    def save_question(self, question: ClarificationQuestion) -> None:
        try:
            with self._store.connection() as connection:
                cursor = connection.execute(
                    """
                    UPDATE analysis_questions SET payload = %s, updated_at = now()
                    WHERE question_id = %s AND requirement_id = %s
                      AND (payload->>'version')::integer = %s
                    """,
                    (
                        Jsonb(clarification_question_to_payload(question)),
                        question.id.value,
                        question.requirement_id.value,
                        question.version - 1,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ClarificationVersionConflictError(
                        "Question changed since it was loaded. Refresh and try again."
                    )
                self._store.mark_requirement_dirty(question.requirement_id)
        except RaiseException as exc:
            raise InvalidClarificationTransitionError(
                "Resolved or superseded questions cannot be changed."
            ) from exc

    def get_question(
        self, requirement_id: RequirementId, question_id: QuestionId
    ) -> ClarificationQuestion | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """
                SELECT payload FROM analysis_questions
                WHERE requirement_id = %s AND question_id = %s
                """,
                (requirement_id.value, question_id.value),
            ).fetchone()
        return clarification_question_from_payload(_payload(row[0])) if row is not None else None

    def list_questions(self, requirement_id: RequirementId) -> list[ClarificationQuestion]:
        with self._store.connection() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM analysis_questions
                WHERE requirement_id = %s ORDER BY created_at, question_id
                """,
                (requirement_id.value,),
            ).fetchall()
        return [clarification_question_from_payload(_payload(row[0])) for row in rows]
