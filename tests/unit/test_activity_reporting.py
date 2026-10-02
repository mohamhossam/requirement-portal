from __future__ import annotations

from datetime import UTC, datetime, timedelta

from smb_requirement_agent.application.ports.activity import (
    ActivityAction,
    ActivityCategory,
    ActivityEvent,
    ActivityReportEvidence,
    ActivityResult,
    AuditSourceKind,
    AuditSourceReference,
    BlockerEvidence,
)
from smb_requirement_agent.application.use_cases.activity_reporting import (
    ActivityQuery,
    GetOperationalReport,
    ListActivity,
    aggregate_activity_events,
)
from smb_requirement_agent.domain.identity.entities import ActorId, ActorSnapshot
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.infrastructure.time.fixed_clock import FixedClock

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)
REQUIREMENT_ID = RequirementId("req-1")
ACTOR = ActorSnapshot(ActorId("actor-1"), "Reviewer")


def event(
    event_id: str,
    action: ActivityAction,
    occurred_at: datetime,
    *,
    actor: ActorSnapshot | None = ACTOR,
    target_id: str | None = None,
) -> ActivityEvent:
    return ActivityEvent(
        event_id,
        REQUIREMENT_ID,
        "Fibre offer",
        ActivityCategory.CLARIFICATION,
        action,
        action.value,
        occurred_at,
        actor,
        target_id,
        "/requirements/req-1/clarify",
        (AuditSourceReference(AuditSourceKind.CLARIFICATION_QUESTION, event_id),),
    )


class Evidence:
    def __init__(
        self, events: list[ActivityEvent], blockers: list[BlockerEvidence] | None = None
    ) -> None:
        self.events = events
        self.blockers = blockers or []

    def list_events(self) -> list[ActivityEvent]:
        return list(self.events)

    def query(self, query: ActivityQuery) -> ActivityResult:
        matches = [event for event in self.events if ListActivity.matches(event, query)]
        matches.sort(key=lambda event: event.id, reverse=True)
        matches.sort(key=lambda event: event.occurred_at, reverse=True)
        items = tuple(matches[query.offset : query.offset + query.limit])
        return ActivityResult(
            items, len(matches), query.offset, query.limit, query.offset + len(items) < len(matches)
        )

    def aggregate_report(self, start: datetime, before: datetime) -> ActivityReportEvidence:
        return aggregate_activity_events(self.window_events(start, before))

    def window_events(self, start: datetime, before: datetime) -> list[ActivityEvent]:
        return [event for event in self.events if start <= event.occurred_at < before]

    def list_events_for_requirement(self, requirement_id: RequirementId) -> list[ActivityEvent]:
        return [event for event in self.events if event.requirement_id == requirement_id]

    def list_current_blockers(self) -> list[BlockerEvidence]:
        return list(self.blockers)


def test_activity_filters_orders_and_paginates_with_exclusive_end() -> None:
    events = [
        event("b", ActivityAction.QUESTION_ASKED, NOW - timedelta(hours=2)),
        event("a", ActivityAction.QUESTION_RESOLVED, NOW - timedelta(hours=1)),
        event("c", ActivityAction.QUESTION_RESOLVED, NOW - timedelta(hours=1), actor=None),
    ]

    result = ListActivity(Evidence(events)).execute(
        ActivityQuery(
            actions=frozenset({ActivityAction.QUESTION_RESOLVED}),
            occurred_before=NOW,
            offset=1,
            limit=1,
        )
    )

    assert result.total == 2
    assert [item.id for item in result.items] == ["a"]
    assert result.has_more is False
    assert result.items[0].actor == ACTOR


def test_report_uses_monday_utc_partial_week_and_clarification_cohort() -> None:
    monday = datetime(2026, 8, 31, tzinfo=UTC)
    opened_one = event(
        "opened-1", ActivityAction.QUESTION_ASKED, monday + timedelta(hours=1), target_id="q1"
    )
    opened_two = event(
        "opened-2", ActivityAction.QUESTION_ASKED, monday + timedelta(hours=2), target_id="q2"
    )
    resolved_one = event(
        "resolved-1",
        ActivityAction.QUESTION_RESOLVED,
        monday + timedelta(hours=5),
        target_id="q1",
    )
    created = event("created", ActivityAction.REQUIREMENT_CREATED, monday)
    future = event("future", ActivityAction.BREAKDOWN_APPROVED, NOW + timedelta(minutes=1))
    old_resolution = event(
        "old-resolution",
        ActivityAction.QUESTION_RESOLVED,
        monday - timedelta(hours=1),
        target_id="old-question",
    )
    evidence = Evidence([opened_one, opened_two, resolved_one, created, future, old_resolution])

    report = GetOperationalReport(evidence, evidence, FixedClock(NOW)).execute(4)

    assert report.window_start == datetime(2026, 8, 10, tzinfo=UTC)
    assert report.window_end == NOW
    assert report.weekly[-1].week_start == monday
    assert report.weekly[-1].week_end == NOW
    assert report.weekly[-1].requirements_created.value == 1
    assert report.weekly[-1].requirements_created.evidence_event_ids == ("created",)
    assert report.weekly[-1].breakdown_approvals.value == 0
    assert report.clarification.opened.value == 2
    assert report.clarification.resolved.value == 1
    assert report.clarification.resolution_percentage == 50.0
    assert report.clarification.median_resolution_hours == 4.0


def test_report_orders_and_limits_current_blockers() -> None:
    blockers = [
        BlockerEvidence(
            f"blocker-{index:02}",
            REQUIREMENT_ID,
            "Fibre offer",
            f"Blocker {index}",
            NOW - timedelta(days=index),
            None,
            "/requirements/req-1/review",
            AuditSourceReference(AuditSourceKind.REVIEW_DECISION, f"flag-{index}"),
        )
        for index in range(12)
    ]
    evidence = Evidence([], blockers)

    report = GetOperationalReport(evidence, evidence, FixedClock(NOW)).execute()

    assert len(report.oldest_blockers) == 10
    assert report.oldest_blockers[0].id == "blocker-11"
    assert report.oldest_blockers[-1].id == "blocker-02"
