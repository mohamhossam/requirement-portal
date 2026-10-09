"""Persistence boundary for reusable Feature quality snapshots."""

from typing import Protocol

from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.quality import FeatureQualitySnapshot


class StoryQualityRepositoryPort(Protocol):
    def get(self, feature_id: FeatureId) -> FeatureQualitySnapshot | None: ...

    def save(self, snapshot: FeatureQualitySnapshot) -> None: ...
