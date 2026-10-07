"""Compose current snapshots and immutable histories for activity normalization."""

from contextlib import AbstractContextManager
from typing import Any, cast

from smb_requirement_agent.analysis.domain.entities import AnalysisRound, ClarificationQuestion
from smb_requirement_agent.analysis.infrastructure.analysis_payloads import (
    analysis_round_from_payload,
    clarification_question_from_payload,
)
from smb_requirement_agent.application.ports.requirement_worklist import RequirementWorklistSnapshot
from smb_requirement_agent.domain.revision.entities import BreakdownRevision, RequirementRevision
from smb_requirement_agent.infrastructure.persistence.postgres_activity_reader import (
    ActivityInputDelta,
)
from smb_requirement_agent.infrastructure.persistence.postgres_requirement_knowledge import (
    finding_from_payload,
)
from smb_requirement_agent.infrastructure.persistence.postgres_revisions import (
    PostgresRevisionRepository,
)
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_snapshots import (
    PostgresSnapshotReader,
)
from smb_requirement_agent.infrastructure.persistence.postgres_values import _payload
from smb_requirement_agent.jobs.infrastructure.postgres_ai_jobs import record_from_row
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class PostgresActivitySources:
    def __init__(
        self,
        session: PostgresSession,
        snapshots: PostgresSnapshotReader,
        revisions: PostgresRevisionRepository,
    ) -> None:
        self._session = session
        self._snapshots = snapshots
        self._revisions = revisions

    def transaction(self) -> AbstractContextManager[None]:
        return self._session.transaction()

    def activity_inputs(
        self, requirement_id: RequirementId, active_round_ids: tuple[str, ...], access_version: int
    ) -> ActivityInputDelta:
        key = requirement_id.value
        with self._session.connection() as connection:
            rounds = connection.execute(
                "SELECT r.payload FROM analysis_rounds r LEFT JOIN activity_input_cursors c "
                "ON c.requirement_id=r.requirement_id AND c.source_kind='round' "
                "AND c.source_id=r.analysis_id "
                "WHERE r.requirement_id=%s AND (c.source_id IS NULL OR r.analysis_id=ANY(%s) "
                "OR EXISTS (SELECT 1 FROM analysis_questions q LEFT JOIN activity_input_cursors qc "
                "ON qc.requirement_id=q.requirement_id AND qc.source_kind='question' "
                "AND qc.source_id=q.question_id WHERE q.first_analysis_id=r.analysis_id "
                "AND qc.source_version IS DISTINCT FROM COALESCE(q.payload->>'version','1'))) "
                "ORDER BY r.round_number",
                (key, list(active_round_ids)),
            ).fetchall()
            questions = connection.execute(
                "SELECT q.payload FROM analysis_questions q LEFT JOIN activity_input_cursors c "
                "ON c.requirement_id=q.requirement_id AND c.source_kind='question' "
                "AND c.source_id=q.question_id WHERE q.requirement_id=%s "
                "AND c.source_version IS DISTINCT FROM COALESCE(q.payload->>'version','1')",
                (key,),
            ).fetchall()
            jobs = connection.execute(
                "SELECT j.* FROM ai_jobs j LEFT JOIN activity_input_cursors c "
                "ON c.requirement_id=j.requirement_id AND c.source_kind='job' "
                "AND c.source_id=j.job_id "
                "WHERE j.requirement_id=%s AND c.source_version IS DISTINCT FROM j.version::text",
                (key,),
            ).fetchall()
            findings = connection.execute(
                "SELECT f.payload FROM requirement_knowledge_findings f "
                "LEFT JOIN activity_input_cursors c "
                "ON c.requirement_id=%s AND c.source_kind='finding' AND c.source_id=f.finding_id "
                "WHERE (f.subject_requirement_id=%s OR f.related_requirement_id=%s) "
                "AND c.source_version IS DISTINCT FROM COALESCE(f.payload->>'version','1')",
                (key, key, key),
            ).fetchall()
            access = connection.execute(
                "SELECT source_version FROM activity_input_cursors WHERE requirement_id=%s "
                "AND source_kind='access' AND source_id=%s",
                (key, key),
            ).fetchone()
        decoded_rounds = [analysis_round_from_payload(_payload(row[0])) for row in rounds]
        decoded_questions = [
            clarification_question_from_payload(_payload(row[0])) for row in questions
        ]
        decoded_jobs = [record_from_row(row) for row in jobs]
        decoded_findings = tuple(
            finding_from_payload(cast(dict[str, Any], row[0])) for row in findings
        )
        versions = (
            [("round", item.id.value, "1") for item in decoded_rounds]
            + [("question", item.id.value, str(item.version)) for item in decoded_questions]
            + [("job", item.job.id.value, str(item.job.version)) for item in decoded_jobs]
            + [("finding", item.id.value, str(item.version)) for item in decoded_findings]
            + [("access", key, str(access_version))]
        )
        return ActivityInputDelta(
            decoded_rounds,
            decoded_questions,
            decoded_jobs,
            decoded_findings,
            access is None or str(access[0]) != str(access_version),
            tuple(versions),
        )

    def list_snapshots(
        self, requirement_ids: tuple[str, ...] | None = None
    ) -> list[RequirementWorklistSnapshot]:
        return self._snapshots.list_snapshots(requirement_ids)

    def list_requirement_revisions(
        self, requirement_id: RequirementId, *, after: int = 0
    ) -> list[RequirementRevision]:
        return self._revisions.list_requirement_revisions(requirement_id, after=after)

    def list_breakdown_revisions(
        self, requirement_id: RequirementId, *, after: int = 0
    ) -> list[BreakdownRevision]:
        return self._revisions.list_breakdown_revisions(requirement_id, after=after)

    def load_activity_history(
        self,
    ) -> tuple[
        dict[str, list[RequirementRevision]],
        dict[str, list[BreakdownRevision]],
        dict[str, list[AnalysisRound]],
        dict[str, list[ClarificationQuestion]],
    ]:
        return self._revisions.load_activity_history()
