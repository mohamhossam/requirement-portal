"""Invalidation of artifacts derived from a requirement or its Epic.

When something changes, everything derived from it is out of date. What that
means differs by artifact, and the difference is deliberate (ADR-0004):

- an **analysis** is disposable AI output that no human has approved, so it is
  deleted and simply regenerated;
- an **Epic** and its **Features** may carry a human edit or approval, so they
  are flagged stale and never destroyed. AGENTS.md section 8 forbids silently
  discarding approved content.

Since ADR-0103 this class only publishes the domain event for the change. The
rules live in the handlers that `interfaces/api/composition/events.py`
subscribes, in this order:

- governance: `InvalidateApprovalWorkflow.on_change` resets the review;
- analysis: `DiscardAnalysis` deletes the analysis and supersedes its questions;
- breakdown: `MarkBacklogStale` flags the Epic, Features and Stories.

PR 5 of the migration has the call sites publish these events themselves and
removes this facade.
"""

from __future__ import annotations

from smb_requirement_agent.application.ports.domain_events import DomainEventPublisher
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.epic.events import EpicChanged
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.events import FeatureChanged
from smb_requirement_agent.domain.requirement.events import RequirementRevised
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class InvalidateDerivedArtifacts:
    """Publishes the change; the subscribed handlers apply the invalidation rules."""

    def __init__(self, events: DomainEventPublisher) -> None:
        self._events = events

    def for_changed_requirement(self, requirement_id: RequirementId) -> None:
        """The requirement text changed: everything below it is out of date."""
        self._events.publish(RequirementRevised(requirement_id=requirement_id))

    def for_changed_epic(self, epic: Epic) -> None:
        """The Epic was regenerated or edited: its Features no longer match it."""
        self._events.publish(EpicChanged(requirement_id=epic.requirement_id, epic_id=epic.id))

    def for_changed_feature(self, requirement_id: RequirementId, feature: Feature) -> None:
        """The Feature changed: preserve its Stories but flag their divergence."""
        self._events.publish(FeatureChanged(requirement_id=requirement_id, feature_id=feature.id))
