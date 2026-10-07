"""Focused PostgreSQL persistence adapter."""

from __future__ import annotations

from datetime import datetime

from smb_requirement_agent.application.ports.requirement_worklist import (
    RequirementWorklistSnapshot,
)
from smb_requirement_agent.domain.analysis.entities import (
    ClarificationQuestion,
)
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.jobs.entities import AiJobOperation
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.identity.infrastructure.identity_payloads import access_from_payload
from smb_requirement_agent.infrastructure.persistence.analysis_payloads import (
    analysis_from_payload,
    clarification_question_from_payload,
)
from smb_requirement_agent.infrastructure.persistence.backlog_payloads import (
    epic_from_payload,
    feature_from_payload,
    story_from_payload,
)
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import (
    _datetime,
    _payload,
    _string,
)
from smb_requirement_agent.infrastructure.persistence.requirement_snapshot import (
    requirement_from_payload,
)
from smb_requirement_agent.infrastructure.persistence.review_payloads import review_from_payload


class PostgresSnapshotReader:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def list_snapshots(
        self, requirement_ids: tuple[str, ...] | None = None
    ) -> list[RequirementWorklistSnapshot]:
        """Load the complete worklist in bounded bulk queries.

        Filtering and paging remain application policy, while this adapter
        avoids one database round trip per aggregate in a portfolio view.
        """
        if requirement_ids == ():
            return []
        clause = "" if requirement_ids is None else " WHERE requirement_id=ANY(%s)"
        parameters = () if requirement_ids is None else (list(requirement_ids),)
        with self._store.connection() as connection:
            requirement_rows = connection.execute(
                "SELECT requirement_id, payload, updated_at FROM requirements" + clause,
                parameters,
            ).fetchall()
            analysis_rows = connection.execute(
                "SELECT requirement_id, payload, updated_at FROM requirement_analyses" + clause,
                parameters,
            ).fetchall()
            epic_rows = connection.execute(
                "SELECT requirement_id, payload, updated_at FROM epics" + clause,
                parameters,
            ).fetchall()
            joined_clause = "" if requirement_ids is None else " WHERE e.requirement_id=ANY(%s)"
            feature_rows = connection.execute(
                """
                SELECT e.requirement_id, f.payload, f.updated_at
                FROM features f JOIN epics e ON e.epic_id = f.epic_id
                """
                + joined_clause
                + " ORDER BY e.requirement_id, f.position",
                parameters,
            ).fetchall()
            story_rows = connection.execute(
                """
                SELECT e.requirement_id, s.payload, s.updated_at
                FROM stories s
                JOIN features f ON f.feature_id = s.feature_id
                JOIN epics e ON e.epic_id = f.epic_id
                """
                + joined_clause
                + " ORDER BY e.requirement_id, f.position, s.position",
                parameters,
            ).fetchall()
            activity_filter = "" if requirement_ids is None else " WHERE requirement_id=ANY(%s)"
            activity_rows = connection.execute(
                """
                SELECT requirement_id, max(created_at)
                FROM (
                    SELECT requirement_id, created_at FROM requirement_revisions
                    UNION ALL
                    SELECT requirement_id, created_at FROM breakdown_revisions
                ) revision_activity
                """
                + activity_filter
                + """
                GROUP BY requirement_id
                """,
                parameters,
            ).fetchall()
            access_rows = connection.execute(
                "SELECT requirement_id, payload, updated_at FROM requirement_access" + clause,
                parameters,
            ).fetchall()
            question_rows = connection.execute(
                "SELECT requirement_id, payload, updated_at FROM analysis_questions" + clause,
                parameters,
            ).fetchall()
            job_clause = "" if requirement_ids is None else " AND requirement_id=ANY(%s)"
            active_job_rows = connection.execute(
                """
                SELECT DISTINCT ON (requirement_id) requirement_id, operation, updated_at
                FROM ai_jobs
                WHERE status IN ('queued','running','cancellation_requested')
                """
                + job_clause
                + " ORDER BY requirement_id, created_at",
                parameters,
            ).fetchall()
            review_rows = connection.execute(
                "SELECT requirement_id, payload, updated_at FROM breakdown_reviews" + clause,
                parameters,
            ).fetchall()

        analyses = {
            _string(row[0]): (analysis_from_payload(_payload(row[1])), _datetime(row[2]))
            for row in analysis_rows
        }
        epics = {
            _string(row[0]): (epic_from_payload(_payload(row[1])), _datetime(row[2]))
            for row in epic_rows
        }
        features: dict[str, list[tuple[Feature, datetime]]] = {}
        for row in feature_rows:
            features.setdefault(_string(row[0]), []).append(
                (feature_from_payload(_payload(row[1])), _datetime(row[2]))
            )
        stories: dict[str, list[tuple[UserStory, datetime]]] = {}
        for row in story_rows:
            stories.setdefault(_string(row[0]), []).append(
                (story_from_payload(_payload(row[1])), _datetime(row[2]))
            )
        latest_activity = {_string(row[0]): _datetime(row[1]) for row in activity_rows}
        accesses = {
            _string(row[0]): (access_from_payload(_payload(row[1])), _datetime(row[2]))
            for row in access_rows
        }
        questions: dict[str, list[tuple[ClarificationQuestion, datetime]]] = {}
        for row in question_rows:
            questions.setdefault(_string(row[0]), []).append(
                (clarification_question_from_payload(_payload(row[1])), _datetime(row[2]))
            )
        active_jobs = {
            _string(row[0]): (AiJobOperation(_string(row[1])), _datetime(row[2]))
            for row in active_job_rows
        }
        reviews = {
            _string(row[0]): (review_from_payload(_payload(row[1])), _datetime(row[2]))
            for row in review_rows
        }

        snapshots: list[RequirementWorklistSnapshot] = []
        for row in requirement_rows:
            raw_id = _string(row[0])
            requirement = requirement_from_payload(_payload(row[1]))
            analysis_entry = analyses.get(raw_id)
            epic_entry = epics.get(raw_id)
            feature_entries = features.get(raw_id, [])
            story_entries = stories.get(raw_id, [])
            access_entry = accesses.get(raw_id)
            question_entries = questions.get(raw_id, [])
            active_job_entry = active_jobs.get(raw_id)
            review_entry = reviews.get(raw_id)
            snapshots.append(
                RequirementWorklistSnapshot(
                    requirement=requirement,
                    analysis=analysis_entry[0] if analysis_entry is not None else None,
                    epic=epic_entry[0] if epic_entry is not None else None,
                    features=tuple(entry[0] for entry in feature_entries),
                    stories=tuple(entry[0] for entry in story_entries),
                    updated_at=max(
                        latest_activity.get(raw_id, _datetime(row[2])),
                        access_entry[1] if access_entry is not None else _datetime(row[2]),
                        *(entry[1] for entry in question_entries),
                        active_job_entry[1] if active_job_entry is not None else _datetime(row[2]),
                        review_entry[1] if review_entry is not None else _datetime(row[2]),
                    ),
                    access=access_entry[0] if access_entry is not None else None,
                    questions=tuple(entry[0] for entry in question_entries),
                    active_ai_operation=(
                        active_job_entry[0] if active_job_entry is not None else None
                    ),
                    review=review_entry[0] if review_entry is not None else None,
                )
            )
        return snapshots
