"""The activity projection over PostgreSQL: incremental inputs, one projection per read.

`RepositoryActivityProjection` (activity_projection.py) derives events the same
way in memory and here; this module only feeds it from PostgreSQL rows and
keeps the incrementally projected state.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

from smb_requirement_agent.analysis.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.analysis.domain.entities import AnalysisRound, ClarificationQuestion
from smb_requirement_agent.application.ports.activity import (
    ActivityEvent,
    ActivityQuery,
    ActivityReadPort,
    ActivityReportEvidence,
    ActivityResult,
    BlockerEvidence,
    ReportingReadPort,
)
from smb_requirement_agent.application.ports.requirement_knowledge import (
    RequirementKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_worklist import (
    RequirementWorklistSnapshot,
)
from smb_requirement_agent.application.use_cases.activity_reporting import (
    aggregate_activity_events,
)
from smb_requirement_agent.domain.knowledge.entities import (
    KnowledgeFinding,
)
from smb_requirement_agent.domain.review.entities import (
    BreakdownStatus,
)
from smb_requirement_agent.domain.revision.entities import BreakdownRevision, RequirementRevision
from smb_requirement_agent.infrastructure.persistence.activity_projection import (
    ActivityJobSource,
    RepositoryActivityProjection,
)
from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobRecord
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class _PostgresActivityStore(Protocol):
    def activity_inputs(
        self, requirement_id: RequirementId, active_round_ids: tuple[str, ...], access_version: int
    ) -> ActivityInputDelta: ...

    def transaction(self) -> AbstractContextManager[None]: ...

    def list_requirement_revisions(
        self, requirement_id: RequirementId, *, after: int = 0
    ) -> list[RequirementRevision]: ...

    def list_breakdown_revisions(
        self, requirement_id: RequirementId, *, after: int = 0
    ) -> list[BreakdownRevision]: ...

    def list_snapshots(
        self, requirement_ids: tuple[str, ...] | None = None
    ) -> list[RequirementWorklistSnapshot]: ...

    def load_activity_history(
        self,
    ) -> tuple[
        dict[str, list[RequirementRevision]],
        dict[str, list[BreakdownRevision]],
        dict[str, list[AnalysisRound]],
        dict[str, list[ClarificationQuestion]],
    ]: ...


class _PostgresActivityJobs(ActivityJobSource, Protocol):
    def list_all_for_activity(self) -> dict[str, list[AiJobRecord]]: ...


class _SnapshotLookup:
    def __init__(self, snapshots: list[RequirementWorklistSnapshot]) -> None:
        self._snapshots = snapshots

    def list_snapshots(
        self, requirement_ids: tuple[str, ...] | None = None
    ) -> list[RequirementWorklistSnapshot]:
        if requirement_ids is None:
            return self._snapshots
        selected = set(requirement_ids)
        return [item for item in self._snapshots if item.requirement.id.value in selected]


class _RevisionLookup:
    def __init__(
        self,
        requirements: dict[str, list[RequirementRevision]],
        breakdowns: dict[str, list[BreakdownRevision]],
    ) -> None:
        self._requirements = requirements
        self._breakdowns = breakdowns

    def list_requirement_revisions(
        self, requirement_id: RequirementId
    ) -> list[RequirementRevision]:
        return self._requirements.get(requirement_id.value, [])

    def list_breakdown_revisions(self, requirement_id: RequirementId) -> list[BreakdownRevision]:
        return self._breakdowns.get(requirement_id.value, [])


class _AnalysisLookup:
    def __init__(
        self,
        rounds: dict[str, list[AnalysisRound]],
        questions: dict[str, list[ClarificationQuestion]],
    ) -> None:
        self._rounds = rounds
        self._questions = questions

    def list_rounds(self, requirement_id: RequirementId) -> list[AnalysisRound]:
        return self._rounds.get(requirement_id.value, [])

    def list_questions(self, requirement_id: RequirementId) -> list[ClarificationQuestion]:
        return self._questions.get(requirement_id.value, [])


class _JobLookup:
    def __init__(self, jobs: dict[str, list[AiJobRecord]]) -> None:
        self._jobs = jobs

    def list_for_requirement(
        self, requirement_id: RequirementId, *, active_only: bool = False
    ) -> list[AiJobRecord]:
        records = self._jobs.get(requirement_id.value, [])
        if not active_only:
            return records
        return [item for item in records if not item.job.status.terminal]


@dataclass(frozen=True)
class ActivityInputDelta:
    rounds: list[AnalysisRound]
    questions: list[ClarificationQuestion]
    jobs: list[AiJobRecord]
    findings: tuple[KnowledgeFinding, ...]
    access_changed: bool
    source_versions: tuple[tuple[str, str, str], ...]


class _KnowledgeLookup:
    def __init__(self, findings: tuple[KnowledgeFinding, ...]) -> None:
        self._findings = findings

    def list_related_findings(self, requirement_id: RequirementId) -> tuple[KnowledgeFinding, ...]:
        return self._findings


@dataclass(frozen=True)
class ActivityProjectionDelta:
    events: list[ActivityEvent]
    blockers: list[BlockerEvidence]
    requirement_revision: int
    breakdown_revision: int
    review_status: BreakdownStatus | None
    first_recorded_at: datetime
    source_versions: tuple[tuple[str, str, str], ...]


class PostgresActivityReadAdapter(ActivityReadPort, ReportingReadPort):
    """Durable projection loaded in bounded, portfolio-wide bulk queries."""

    def __init__(
        self,
        store: _PostgresActivityStore,
        jobs: _PostgresActivityJobs,
        knowledge: RequirementKnowledgeRepositoryPort,
        analysis_audit: AnalysisAuditRepositoryPort,
    ) -> None:
        self._store = store
        self._jobs = jobs
        self._knowledge = knowledge
        self._analysis_audit = analysis_audit

    def list_events(self) -> list[ActivityEvent]:
        return self._projection().list_events()

    def project_since(
        self,
        requirement_id: RequirementId,
        requirement_revision: int,
        breakdown_revision: int,
        review_status: BreakdownStatus | None,
        first_recorded_at: datetime | None,
    ) -> ActivityProjectionDelta:
        snapshots = self._store.list_snapshots((requirement_id.value,))
        requirements = self._store.list_requirement_revisions(
            requirement_id, after=requirement_revision
        )
        breakdowns = self._store.list_breakdown_revisions(requirement_id, after=breakdown_revision)
        first_recorded_at = first_recorded_at or (
            requirements[0].created_at if requirements else snapshots[0].updated_at
        )
        inputs = self._store.activity_inputs(
            requirement_id,
            tuple(
                {
                    q.first_analysis_id.value
                    for q in snapshots[0].questions
                    if q.is_active and q.is_blocker
                }
            ),
            snapshots[0].access.version if snapshots[0].access else 0,
        )
        if snapshots[0].access is not None and not inputs.access_changed:
            snapshots = [replace(snapshots[0], access=replace(snapshots[0].access, changes=()))]
        projection = RepositoryActivityProjection(
            _SnapshotLookup(snapshots),
            _RevisionLookup(
                {requirement_id.value: requirements},
                {requirement_id.value: breakdowns},
            ),
            _AnalysisLookup(
                {requirement_id.value: inputs.rounds}, {requirement_id.value: inputs.questions}
            ),
            _JobLookup({requirement_id.value: inputs.jobs}),
            _KnowledgeLookup(inputs.findings),
            previous_review_status=review_status,
            first_recorded_at=first_recorded_at,
        )
        return ActivityProjectionDelta(
            projection.list_events_for_requirement(requirement_id),
            projection.list_current_blockers(),
            max((item.number.value for item in requirements), default=requirement_revision),
            max((item.number.value for item in breakdowns), default=breakdown_revision),
            next(
                (item.review.status for item in reversed(breakdowns) if item.review), review_status
            ),
            first_recorded_at,
            inputs.source_versions,
        )

    def query(self, query: ActivityQuery) -> ActivityResult:
        return self._projection().query(query)

    def aggregate_report(self, start: datetime, before: datetime) -> ActivityReportEvidence:

        return aggregate_activity_events(self.window_events(start, before))

    def window_events(self, start: datetime, before: datetime) -> list[ActivityEvent]:
        return self._projection().window_events(start, before)

    def list_events_for_requirement(self, requirement_id: RequirementId) -> list[ActivityEvent]:
        with self._store.transaction():
            snapshots = self._store.list_snapshots((requirement_id.value,))
            projection = RepositoryActivityProjection(
                _SnapshotLookup(snapshots),
                self._store,
                self._analysis_audit,
                self._jobs,
                self._knowledge,
            )
            return projection.list_events_for_requirement(requirement_id)

    def list_current_blockers(self) -> list[BlockerEvidence]:
        return self._projection().list_current_blockers()

    def list_blockers_for_requirement(self, requirement_id: RequirementId) -> list[BlockerEvidence]:
        with self._store.transaction():
            snapshots = self._store.list_snapshots((requirement_id.value,))
            projection = RepositoryActivityProjection(
                _SnapshotLookup(snapshots),
                self._store,
                self._analysis_audit,
                self._jobs,
                self._knowledge,
            )
            return projection.list_current_blockers()

    def _projection(self) -> RepositoryActivityProjection:
        with self._store.transaction():
            snapshots = self._store.list_snapshots()
            requirements, breakdowns, rounds, questions = self._store.load_activity_history()
            jobs = self._jobs.list_all_for_activity()
        return RepositoryActivityProjection(
            _SnapshotLookup(snapshots),
            _RevisionLookup(requirements, breakdowns),
            _AnalysisLookup(rounds, questions),
            _JobLookup(jobs),
            self._knowledge,
        )
