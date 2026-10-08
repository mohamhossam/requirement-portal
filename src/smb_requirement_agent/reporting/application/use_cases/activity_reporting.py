"""Portfolio activity filtering and deterministic operational reporting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import InvalidReportingWindowError
from smb_requirement_agent.reporting.application.ports.activity import (
    ActivityAction,
    ActivityEvent,
    ActivityReadPort,
    ActivityReportEvidence,
    BlockerEvidence,
    ReportingReadPort,
    WeeklyActivityEvidence,
)
from smb_requirement_agent.reporting.application.ports.activity import (
    ActivityQuery as ActivityQuery,
)
from smb_requirement_agent.reporting.application.ports.activity import (
    ActivityResult as ActivityResult,
)


class ListActivity:
    def __init__(self, activity: ActivityReadPort) -> None:
        self._activity = activity

    def execute(self, query: ActivityQuery) -> ActivityResult:
        return self._activity.query(query)

    @staticmethod
    def matches(event: ActivityEvent, query: ActivityQuery) -> bool:
        return not any(
            (
                query.requirement_id is not None and event.requirement_id != query.requirement_id,
                query.categories and event.category not in query.categories,
                query.actions and event.action not in query.actions,
                query.actor_id is not None
                and (event.actor is None or event.actor.id != query.actor_id),
                query.occurred_from is not None and event.occurred_at < query.occurred_from,
                query.occurred_before is not None and event.occurred_at >= query.occurred_before,
            )
        )


@dataclass(frozen=True)
class MetricCount:
    value: int
    evidence_event_ids: tuple[str, ...]


@dataclass(frozen=True)
class WeeklyMetrics:
    week_start: datetime
    week_end: datetime
    requirements_created: MetricCount
    analysis_rounds: MetricCount
    clarifications_resolved: MetricCount
    artifact_approvals: MetricCount
    breakdown_approvals: MetricCount


@dataclass(frozen=True)
class ClarificationMetrics:
    opened: MetricCount
    resolved: MetricCount
    resolution_percentage: float
    median_resolution_hours: float | None


@dataclass(frozen=True)
class OperationalReport:
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    weeks: int
    weekly: tuple[WeeklyMetrics, ...]
    clarification: ClarificationMetrics
    oldest_blockers: tuple[BlockerEvidence, ...]


class GetOperationalReport:
    _WEEK_OPTIONS = frozenset({4, 12, 26})

    def __init__(
        self,
        activity: ActivityReadPort,
        reporting: ReportingReadPort,
        clock: ClockPort,
    ) -> None:
        self._activity = activity
        self._reporting = reporting
        self._clock = clock

    def execute(self, weeks: int = 12) -> OperationalReport:
        if weeks not in self._WEEK_OPTIONS:
            raise InvalidReportingWindowError("Reporting weeks must be one of 4, 12, or 26.")
        now = self._clock.now().astimezone(UTC)
        current_week = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start = current_week - timedelta(weeks=weeks - 1)
        evidence = self._activity.aggregate_report(start, now)
        counts = {(item.week_start, item.action): item.event_ids for item in evidence.weekly}

        def week(index: int) -> WeeklyMetrics:
            week_start = start + timedelta(weeks=index)

            def count(action: ActivityAction) -> MetricCount:
                ids = counts.get((week_start, action), ())
                return MetricCount(len(ids), ids)

            return WeeklyMetrics(
                week_start,
                min(week_start + timedelta(weeks=1), now),
                count(ActivityAction.REQUIREMENT_CREATED),
                count(ActivityAction.ANALYSIS_GENERATED),
                count(ActivityAction.QUESTION_RESOLVED),
                count(ActivityAction.ARTIFACT_APPROVED),
                count(ActivityAction.BREAKDOWN_APPROVED),
            )

        weekly = tuple(week(index) for index in range(weeks))
        opened = len(evidence.opened_ids)
        resolved = len(evidence.resolved_ids)
        clarification = ClarificationMetrics(
            MetricCount(opened, evidence.opened_ids),
            MetricCount(resolved, evidence.resolved_ids),
            round(resolved / opened * 100 if opened else 0.0, 1),
            round(evidence.median_resolution_hours, 1)
            if evidence.median_resolution_hours is not None
            else None,
        )
        blockers = tuple(
            sorted(
                self._reporting.list_current_blockers(),
                key=lambda item: (item.opened_at, item.id),
            )[:10]
        )
        return OperationalReport(now, start, now, weeks, weekly, clarification, blockers)


def aggregate_activity_events(events: list[ActivityEvent]) -> ActivityReportEvidence:
    """Offline equivalent of the database aggregation over an already bounded window."""
    events = sorted(events, key=lambda item: (item.occurred_at, item.id))
    weekly: dict[tuple[datetime, ActivityAction], list[str]] = {}
    for event in events:
        day = event.occurred_at.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        week = day - timedelta(days=day.weekday())
        weekly.setdefault((week, event.action), []).append(event.id)
    opened = [event for event in events if event.action is ActivityAction.QUESTION_ASKED]
    resolutions = {
        event.target_id: event
        for event in events
        if event.action is ActivityAction.QUESTION_RESOLVED and event.target_id is not None
    }
    pairs = [
        (event, resolutions[event.target_id]) for event in opened if event.target_id in resolutions
    ]
    hours = [
        (end.occurred_at - start.occurred_at).total_seconds() / 3600
        for start, end in pairs
        if end.occurred_at >= start.occurred_at
    ]
    return ActivityReportEvidence(
        tuple(
            WeeklyActivityEvidence(week, action, tuple(ids))
            for (week, action), ids in weekly.items()
        ),
        tuple(event.id for event in opened),
        tuple(end.id for _, end in pairs),
        float(median(hours)) if hours else None,
    )
