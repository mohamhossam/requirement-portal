"""In-memory Story and proposal repositories."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.entities import StoryChangeProposal, UserStory
from smb_requirement_agent.breakdown.domain.story.value_objects import StoryId, StoryProposalId


class InMemoryStoryRepository:
    def __init__(self) -> None:
        self._store: dict[str, list[UserStory]] = {}
        self._set_versions: dict[str, int] = {}

    def snapshot_state(self) -> Any:
        return deepcopy(
            (
                self._store,
                self._set_versions,
            )
        )

    def restore_state(self, state: Any) -> None:
        (
            self._store,
            self._set_versions,
        ) = deepcopy(state)

    def replace_for_feature(
        self, feature_id: FeatureId, stories: list[UserStory], expected_set_version: int
    ) -> int:
        current = self.set_version(feature_id)
        if current != expected_set_version:
            raise ArtifactVersionConflictError(
                f"Story set changed from version {expected_set_version} to {current}. Reload it."
            )
        self._store[feature_id.value] = list(stories)
        self._set_versions[feature_id.value] = current + 1
        return current + 1

    def set_version(self, feature_id: FeatureId) -> int:
        return self._set_versions.get(feature_id.value, 1)

    def get_by_feature_id(self, feature_id: FeatureId) -> list[UserStory]:
        return list(self._store.get(feature_id.value, []))

    def get(self, feature_id: FeatureId, story_id: StoryId) -> UserStory | None:
        return next(
            (story for story in self._store.get(feature_id.value, []) if story.id == story_id),
            None,
        )

    def save(self, story: UserStory) -> None:
        stories = self._store.get(story.feature_id.value, [])
        current = next((item for item in stories if item.id == story.id), None)
        if current is None:
            raise ArtifactVersionConflictError("The Story no longer exists. Reload it.")
        if current != story and story.version != current.version + 1:
            raise ArtifactVersionConflictError(
                "The Story changed before this mutation could be saved. Reload it."
            )
        self._store[story.feature_id.value] = [
            story if current.id == story.id else current for current in stories
        ]


class InMemoryStoryChangeProposalRepository:
    def __init__(self) -> None:
        self._store: dict[tuple[str, str], StoryChangeProposal] = {}

    def snapshot_state(self) -> Any:
        return deepcopy((self._store,))

    def restore_state(self, state: Any) -> None:
        (self._store,) = deepcopy(state)

    def save(self, proposal: StoryChangeProposal) -> None:
        current = self._store.get((proposal.feature_id.value, proposal.id.value))
        if current is not None and current != proposal and proposal.version != current.version + 1:
            raise ArtifactVersionConflictError(
                "The Story proposal changed before this mutation could be saved. Reload it."
            )
        self._store[(proposal.feature_id.value, proposal.id.value)] = proposal

    def get(
        self, feature_id: FeatureId, proposal_id: StoryProposalId
    ) -> StoryChangeProposal | None:
        return self._store.get((feature_id.value, proposal_id.value))

    def list_for_feature(self, feature_id: FeatureId) -> list[StoryChangeProposal]:
        return [
            proposal
            for (stored_feature_id, _), proposal in self._store.items()
            if stored_feature_id == feature_id.value
        ]

    def delete(self, feature_id: FeatureId, proposal_id: StoryProposalId) -> None:
        self._store.pop((feature_id.value, proposal_id.value), None)

    def delete_for_feature(self, feature_id: FeatureId) -> None:
        self._store = {
            key: proposal for key, proposal in self._store.items() if key[0] != feature_id.value
        }
