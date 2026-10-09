"""Story persistence ports."""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.entities import StoryChangeProposal, UserStory
from smb_requirement_agent.breakdown.domain.story.value_objects import StoryId, StoryProposalId


class StoryRepositoryPort(Protocol):
    def replace_for_feature(
        self, feature_id: FeatureId, stories: list[UserStory], expected_set_version: int
    ) -> int: ...

    def set_version(self, feature_id: FeatureId) -> int: ...

    def get_by_feature_id(self, feature_id: FeatureId) -> list[UserStory]: ...

    def get(self, feature_id: FeatureId, story_id: StoryId) -> UserStory | None: ...

    def save(self, story: UserStory) -> None: ...


class StoryChangeProposalRepositoryPort(Protocol):
    def save(self, proposal: StoryChangeProposal) -> None: ...

    def get(
        self, feature_id: FeatureId, proposal_id: StoryProposalId
    ) -> StoryChangeProposal | None: ...

    def list_for_feature(self, feature_id: FeatureId) -> list[StoryChangeProposal]: ...

    def delete(self, feature_id: FeatureId, proposal_id: StoryProposalId) -> None: ...

    def delete_for_feature(self, feature_id: FeatureId) -> None: ...
