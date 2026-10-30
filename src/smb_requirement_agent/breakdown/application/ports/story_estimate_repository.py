"""Persistence boundary for a Feature's latest size suggestions."""

from typing import Protocol

from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.estimate import FeatureEstimateSuggestions


class StoryEstimateSuggestionRepositoryPort(Protocol):
    def get(self, feature_id: FeatureId) -> FeatureEstimateSuggestions | None: ...

    def save(self, suggestions: FeatureEstimateSuggestions) -> None: ...
