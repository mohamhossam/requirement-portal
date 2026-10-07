"""The backlog's reaction to a changed source (ADR-0003, ADR-0004, ADR-0103 §3).

An Epic, Feature or Story may carry a human edit or approval, so it is flagged stale and never
destroyed. AGENTS.md section 8 forbids silently discarding approved content. Each artifact
keeps the reason it first went stale.
"""

from __future__ import annotations

from datetime import datetime

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.application.ports.feature_repository import FeatureRepositoryPort
from smb_requirement_agent.application.ports.story_repository import StoryRepositoryPort
from smb_requirement_agent.domain.epic.events import EpicChanged
from smb_requirement_agent.domain.epic.value_objects import EpicId
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.events import FeatureChanged
from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.requirement.events import RequirementRevised
from smb_requirement_agent.shared_kernel.staleness import StaleReason


class MarkBacklogStale:
    """Handler for `RequirementRevised`, `EpicChanged` and `FeatureChanged`."""

    def __init__(
        self,
        epics: EpicRepositoryPort,
        features: FeatureRepositoryPort,
        stories: StoryRepositoryPort,
        clock: ClockPort,
    ) -> None:
        self._epics = epics
        self._features = features
        self._stories = stories
        self._clock = clock

    def on_requirement_revised(self, event: RequirementRevised) -> None:
        """The requirement text changed: everything below it is out of date."""
        epic = self._epics.get_by_requirement_id(event.requirement_id)
        if epic is None:
            return
        at = self._clock.now()
        self._epics.save(epic.mark_stale(StaleReason.REQUIREMENT_CHANGED, at))
        self._stale_features(epic.id, StaleReason.REQUIREMENT_CHANGED, at)

    def on_epic_changed(self, event: EpicChanged) -> None:
        """The Epic was regenerated or edited: its Features no longer match it.

        The Epic itself is the thing that changed, so it is not marked stale against itself.
        """
        self._stale_features(event.epic_id, StaleReason.EPIC_CHANGED, self._clock.now())

    def on_feature_changed(self, event: FeatureChanged) -> None:
        """The Feature changed: preserve its Stories but flag their divergence."""
        self._stale_stories(event.feature_id, StaleReason.FEATURE_CHANGED, self._clock.now())

    def _stale_features(self, epic_id: EpicId, reason: StaleReason, at: datetime) -> None:
        features: list[Feature] = self._features.get_by_epic_id(epic_id)
        for feature in features:
            self._stale_stories(feature.id, reason, at)
            self._features.save(feature.mark_stale(reason, at))

    def _stale_stories(self, feature_id: FeatureId, reason: StaleReason, at: datetime) -> None:
        for story in self._stories.get_by_feature_id(feature_id):
            self._stories.save(story.mark_stale(reason, at))
