"""Reporting: the activity feed, the operational report, saved views and the worklist.

The backend-specific readers come from the persistence wiring, as every context's repositories
do; this builder composes reporting's use cases over them (ADR-0103 Amendment 3).
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.interfaces.api.composition.persistence import (
    PersistenceAdapters,
    RequirementWorklistWiring,
)
from smb_requirement_agent.knowledge.application.use_cases.requirement_knowledge import (
    GetKnowledgeReview,
)
from smb_requirement_agent.reporting.application.use_cases.activity_reporting import (
    GetOperationalReport,
    ListActivity,
)
from smb_requirement_agent.reporting.application.use_cases.saved_views import SavedViews


@dataclass(frozen=True)
class ReportingWiring:
    list_activity: ListActivity
    get_operational_report: GetOperationalReport
    saved_views: SavedViews
    worklist: RequirementWorklistWiring


def build_reporting(
    persistence: PersistenceAdapters,
    knowledge_review: GetKnowledgeReview,
    clock: ClockPort,
) -> ReportingWiring:
    return ReportingWiring(
        list_activity=ListActivity(persistence.activity_reader),
        get_operational_report=GetOperationalReport(
            persistence.activity_reader, persistence.reporting_reader, clock
        ),
        saved_views=SavedViews(persistence.saved_view_repository, clock),
        worklist=persistence.worklist(knowledge_review),
    )
