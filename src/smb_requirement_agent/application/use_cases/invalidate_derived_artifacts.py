"""Invalidation of artifacts derived from a requirement or its Epic.

When something changes, everything derived from it is out of date. What that
means differs by artifact, and the difference is deliberate:

- an **analysis** is disposable AI output that no human has approved, so it is
  deleted and simply regenerated;
- an **Epic** and its **Features** may carry a human edit or approval, so they
  are flagged stale and never destroyed. AGENTS.md section 8 forbids silently
  discarding approved content.

Collecting the rules here keeps them out of the use cases that trigger them:
`UpdateRequirement` should not know how far down the tree a text edit reaches,
and `GenerateEpic` should not hand-roll a `mark_stale` call per child.
"""

from __future__ import annotations

from datetime import datetime

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.application.ports.feature_repository import FeatureRepositoryPort
from smb_requirement_agent.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.ports.story_repository import StoryRepositoryPort
from smb_requirement_agent.application.use_cases.invalidate_approval_workflow import (
    InvalidateApprovalWorkflow,
)
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.staleness import StaleReason


class InvalidateDerivedArtifacts:
    """Applies the invalidation rules for one requirement or Epic."""

    def __init__(
        self,
        analysis_repository: RequirementAnalysisRepositoryPort,
        epic_repository: EpicRepositoryPort,
        feature_repository: FeatureRepositoryPort,
        story_repository: StoryRepositoryPort,
        clock: ClockPort,
        audits: AnalysisAuditRepositoryPort,
        approval_workflow: InvalidateApprovalWorkflow,
    ) -> None:
        self._analyses = analysis_repository
        self._epics = epic_repository
        self._features = feature_repository
        self._stories = story_repository
        self._clock = clock
        self._audits = audits
        self._approval_workflow = approval_workflow

    def for_changed_requirement(self, requirement_id: RequirementId) -> None:
        """The requirement text changed: everything below it is out of date."""
        self._approval_workflow.execute(requirement_id)
        self._analyses.delete_by_requirement_id(requirement_id)
        for question in self._audits.list_questions(requirement_id):
            updated = question.supersede()
            if updated != question:
                self._audits.save_question(updated)

        epic = self._epics.get_by_requirement_id(requirement_id)
        if epic is None:
            return

        at = self._clock.now()
        self._epics.save(epic.mark_stale(StaleReason.REQUIREMENT_CHANGED, at))
        self._stale_features(epic, StaleReason.REQUIREMENT_CHANGED, at)

    def for_changed_epic(self, epic: Epic) -> None:
        """The Epic was regenerated or edited: its Features no longer match it.

        The analysis is untouched - it describes the requirement, which has not
        changed - and the Epic itself is the thing that changed, so it is not
        marked stale against itself.
        """
        self._approval_workflow.execute(epic.requirement_id)
        self._stale_features(epic, StaleReason.EPIC_CHANGED, self._clock.now())

    def for_changed_feature(self, requirement_id: RequirementId, feature: Feature) -> None:
        """The Feature changed: preserve its Stories but flag their divergence."""
        self._approval_workflow.execute(requirement_id)
        self._stale_stories(feature, StaleReason.FEATURE_CHANGED, self._clock.now())

    def _stale_features(self, epic: Epic, reason: StaleReason, at: datetime) -> None:
        features = self._features.get_by_epic_id(epic.id)
        if not features:
            return
        for feature in features:
            self._stale_stories(feature, reason, at)
            self._features.save(feature.mark_stale(reason, at))

    def _stale_stories(self, feature: Feature, reason: StaleReason, at: datetime) -> None:
        stories = self._stories.get_by_feature_id(feature.id)
        for story in stories:
            self._stories.save(story.mark_stale(reason, at))
