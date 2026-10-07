"""Domain-event handler subscriptions: the only place a handler is subscribed (ADR-0103 §3).

Handlers run in the order they are subscribed here. That order is the order the direct
invalidation calls ran in before ADR-0103, and `tests/characterisation/test_invalidation_order.py`
pins it. Do not reorder without changing that test deliberately.
"""

from __future__ import annotations

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.events import InProcessEventDispatcher
from smb_requirement_agent.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.application.ports.breakdown_review_repository import (
    BreakdownReviewRepositoryPort,
)
from smb_requirement_agent.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.application.ports.feature_repository import FeatureRepositoryPort
from smb_requirement_agent.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.ports.story_repository import StoryRepositoryPort
from smb_requirement_agent.application.use_cases.discard_analysis import DiscardAnalysis
from smb_requirement_agent.application.use_cases.mark_backlog_stale import MarkBacklogStale
from smb_requirement_agent.application.use_cases.reset_approval_workflow import (
    ResetApprovalWorkflow,
)
from smb_requirement_agent.domain.architecture.events import ArchitectureImpactChanged
from smb_requirement_agent.domain.epic.events import EpicChanged
from smb_requirement_agent.domain.feature.events import FeatureChanged, FeaturesReplaced
from smb_requirement_agent.domain.story.events import StoriesChanged
from smb_requirement_agent.requirements.domain.requirement.events import RequirementRevised


def subscribe_domain_event_handlers(
    events: InProcessEventDispatcher,
    *,
    analyses: RequirementAnalysisRepositoryPort,
    audits: AnalysisAuditRepositoryPort,
    epics: EpicRepositoryPort,
    features: FeatureRepositoryPort,
    stories: StoryRepositoryPort,
    reviews: BreakdownReviewRepositoryPort,
    clock: ClockPort,
) -> None:
    """Who reacts when a Requirement or its breakdown changes (ADR-0004, ADR-0021)."""
    reset = ResetApprovalWorkflow(reviews)
    discard = DiscardAnalysis(analyses, audits)
    stale = MarkBacklogStale(epics, features, stories, clock)

    events.subscribe(RequirementRevised, reset.on_change)
    events.subscribe(RequirementRevised, discard.on_requirement_revised)
    events.subscribe(RequirementRevised, stale.on_requirement_revised)

    events.subscribe(EpicChanged, reset.on_change)
    events.subscribe(EpicChanged, stale.on_epic_changed)

    events.subscribe(FeatureChanged, reset.on_change)
    events.subscribe(FeatureChanged, stale.on_feature_changed)

    # Changes that only alter what the review attests to.
    events.subscribe(FeaturesReplaced, reset.on_change)
    events.subscribe(StoriesChanged, reset.on_change)
    events.subscribe(ArchitectureImpactChanged, reset.on_change)
