"""Focused PostgreSQL persistence adapter."""

from __future__ import annotations

from psycopg.types.json import Jsonb

from smb_requirement_agent.application.errors import (
    PersistenceError,
)
from smb_requirement_agent.domain.analysis.entities import (
    AnalysisRound,
    ClarificationQuestion,
)
from smb_requirement_agent.domain.revision.entities import (
    BreakdownRevision,
    RequirementRevision,
    RevisionNumber,
)
from smb_requirement_agent.identity.infrastructure.identity_payloads import access_from_payload
from smb_requirement_agent.infrastructure.persistence.analysis_payloads import (
    analysis_from_payload,
    analysis_round_from_payload,
    clarification_question_from_payload,
)
from smb_requirement_agent.infrastructure.persistence.backlog_payloads import (
    epic_from_payload,
    feature_from_payload,
    story_from_payload,
)
from smb_requirement_agent.infrastructure.persistence.payload_fields import JsonObject
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import (
    DbConnection,
    _datetime,
    _integer,
    _payload,
    _string,
)
from smb_requirement_agent.infrastructure.persistence.review_payloads import review_from_payload
from smb_requirement_agent.requirements.infrastructure.requirement_snapshot import (
    requirement_from_payload,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class PostgresRevisionRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def list_requirement_revisions(
        self, requirement_id: RequirementId, *, after: int = 0
    ) -> list[RequirementRevision]:
        with self._store.connection() as connection:
            rows = connection.execute(
                """
                SELECT revision_number, created_at, payload
                FROM requirement_revisions WHERE requirement_id = %s AND revision_number > %s
                ORDER BY revision_number
                """,
                (requirement_id.value, after),
            ).fetchall()
        return [
            RequirementRevision(
                requirement_id,
                RevisionNumber(_integer(row[0])),
                _datetime(row[1]),
                requirement_from_payload(_payload(_payload(row[2]).get("requirement", row[2]))),
                (
                    access_from_payload(_payload(_payload(row[2])["access"]))
                    if _payload(row[2]).get("access") is not None
                    else None
                ),
            )
            for row in rows
        ]

    def list_breakdown_revisions(
        self, requirement_id: RequirementId, *, after: int = 0
    ) -> list[BreakdownRevision]:
        with self._store.connection() as connection:
            rows = connection.execute(
                """
                SELECT revision_number, created_at, payload
                FROM breakdown_revisions WHERE requirement_id = %s AND revision_number > %s
                ORDER BY revision_number
                """,
                (requirement_id.value, after),
            ).fetchall()
        return [self._breakdown_revision(requirement_id, row) for row in rows]

    def load_activity_history(
        self,
    ) -> tuple[
        dict[str, list[RequirementRevision]],
        dict[str, list[BreakdownRevision]],
        dict[str, list[AnalysisRound]],
        dict[str, list[ClarificationQuestion]],
    ]:
        """Load all immutable activity sources in a fixed number of queries."""
        with self._store.connection() as connection:
            requirement_rows = connection.execute(
                """
                SELECT requirement_id, revision_number, created_at, payload
                FROM requirement_revisions ORDER BY requirement_id, revision_number
                """
            ).fetchall()
            breakdown_rows = connection.execute(
                """
                SELECT requirement_id, revision_number, created_at, payload
                FROM breakdown_revisions ORDER BY requirement_id, revision_number
                """
            ).fetchall()
            round_rows = connection.execute(
                """
                SELECT requirement_id, payload FROM analysis_rounds
                ORDER BY requirement_id, round_number, analysis_id
                """
            ).fetchall()
            question_rows = connection.execute(
                """
                SELECT requirement_id, payload FROM analysis_questions
                ORDER BY requirement_id, created_at, question_id
                """
            ).fetchall()
        requirements: dict[str, list[RequirementRevision]] = {}
        for row in requirement_rows:
            raw_id = str(row[0])
            requirement_id = RequirementId(raw_id)
            payload = _payload(row[3])
            requirements.setdefault(raw_id, []).append(
                RequirementRevision(
                    requirement_id,
                    RevisionNumber(_integer(row[1])),
                    _datetime(row[2]),
                    requirement_from_payload(_payload(payload.get("requirement", row[3]))),
                    (
                        access_from_payload(_payload(payload["access"]))
                        if payload.get("access") is not None
                        else None
                    ),
                )
            )
        breakdowns: dict[str, list[BreakdownRevision]] = {}
        for row in breakdown_rows:
            raw_id = str(row[0])
            breakdowns.setdefault(raw_id, []).append(
                self._breakdown_revision(RequirementId(raw_id), row[1:])
            )
        rounds: dict[str, list[AnalysisRound]] = {}
        for row in round_rows:
            rounds.setdefault(str(row[0]), []).append(analysis_round_from_payload(_payload(row[1])))
        questions: dict[str, list[ClarificationQuestion]] = {}
        for row in question_rows:
            questions.setdefault(str(row[0]), []).append(
                clarification_question_from_payload(_payload(row[1]))
            )
        return requirements, breakdowns, rounds, questions

    def get_breakdown_revision(
        self, requirement_id: RequirementId, number: RevisionNumber
    ) -> BreakdownRevision | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """
                SELECT revision_number, created_at, payload FROM breakdown_revisions
                WHERE requirement_id = %s AND revision_number = %s
                """,
                (requirement_id.value, number.value),
            ).fetchone()
        return self._breakdown_revision(requirement_id, row) if row is not None else None

    @staticmethod
    def _breakdown_revision(
        requirement_id: RequirementId, row: tuple[object, ...]
    ) -> BreakdownRevision:
        payload = _payload(row[2])
        analysis_data = payload.get("analysis")
        epic_data = payload.get("epic")
        raw_features = payload.get("features", [])
        raw_stories = payload.get("stories", [])
        review_data = payload.get("review")
        if not isinstance(raw_features, list):
            raise PersistenceError("Stored breakdown Features must be an array.")
        if not isinstance(raw_stories, list):
            raise PersistenceError("Stored breakdown Stories must be an array.")
        return BreakdownRevision(
            requirement_id,
            RevisionNumber(_integer(row[0])),
            _datetime(row[1]),
            analysis_from_payload(_payload(analysis_data)) if analysis_data is not None else None,
            epic_from_payload(_payload(epic_data)) if epic_data is not None else None,
            tuple(feature_from_payload(_payload(item)) for item in raw_features),
            tuple(story_from_payload(_payload(item)) for item in raw_stories),
            review_from_payload(_payload(review_data)) if review_data is not None else None,
        )

    def create_current_revisions(self, requirement_id: RequirementId) -> None:
        with self._store.connection():
            self._store.mark_requirement_dirty(requirement_id)


class PostgresRevisionWriter:
    def capture(self, requirement_id: RequirementId, connection: DbConnection) -> None:
        requirement_row = connection.execute(
            "SELECT payload FROM requirements WHERE requirement_id = %s FOR UPDATE",
            (requirement_id.value,),
        ).fetchone()
        if requirement_row is None:
            return
        requirement_payload = _payload(requirement_row[0])
        access_row = connection.execute(
            "SELECT payload FROM requirement_access WHERE requirement_id = %s",
            (requirement_id.value,),
        ).fetchone()
        revision_payload: JsonObject = {
            "requirement": requirement_payload,
            "access": _payload(access_row[0]) if access_row is not None else None,
        }
        self._append_if_changed(
            connection, "requirement_revisions", requirement_id, revision_payload
        )

        analysis_row = connection.execute(
            "SELECT payload FROM requirement_analyses WHERE requirement_id = %s",
            (requirement_id.value,),
        ).fetchone()
        epic_row = connection.execute(
            "SELECT epic_id, payload FROM epics WHERE requirement_id = %s",
            (requirement_id.value,),
        ).fetchone()
        review_row = connection.execute(
            "SELECT payload FROM breakdown_reviews WHERE requirement_id = %s",
            (requirement_id.value,),
        ).fetchone()
        feature_payloads: list[object] = []
        story_payloads: list[object] = []
        if epic_row is not None:
            feature_payloads = [
                _payload(row[0])
                for row in connection.execute(
                    "SELECT payload FROM features WHERE epic_id = %s ORDER BY position",
                    (_string(epic_row[0]),),
                ).fetchall()
            ]
            story_payloads = [
                _payload(row[0])
                for row in connection.execute(
                    """
                    SELECT s.payload FROM stories s
                    JOIN features f ON f.feature_id = s.feature_id
                    WHERE f.epic_id = %s ORDER BY f.position, s.position
                    """,
                    (_string(epic_row[0]),),
                ).fetchall()
            ]
        if (
            analysis_row is None
            and epic_row is None
            and not feature_payloads
            and not story_payloads
            and review_row is None
        ):
            return
        breakdown_payload: JsonObject = {
            "analysis": _payload(analysis_row[0]) if analysis_row is not None else None,
            "epic": _payload(epic_row[1]) if epic_row is not None else None,
            "features": feature_payloads,
            "stories": story_payloads,
            "review": _payload(review_row[0]) if review_row is not None else None,
        }
        self._append_if_changed(
            connection, "breakdown_revisions", requirement_id, breakdown_payload
        )

    @staticmethod
    def _append_if_changed(
        connection: DbConnection,
        table: str,
        requirement_id: RequirementId,
        payload: JsonObject,
    ) -> None:
        # table is selected exclusively by this adapter, never caller input.
        latest = connection.execute(
            f"SELECT revision_number, payload FROM {table} "  # noqa: S608
            "WHERE requirement_id = %s ORDER BY revision_number DESC LIMIT 1",
            (requirement_id.value,),
        ).fetchone()
        if latest is not None and _payload(latest[1]) == payload:
            return
        next_number = 1 if latest is None else _integer(latest[0]) + 1
        connection.execute(
            f"INSERT INTO {table} (requirement_id, revision_number, payload) "  # noqa: S608
            "VALUES (%s, %s, %s)",
            (requirement_id.value, next_number, Jsonb(payload)),
        )
