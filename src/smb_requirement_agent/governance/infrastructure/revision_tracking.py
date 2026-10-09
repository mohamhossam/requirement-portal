"""Repository decorators that checkpoint offline in-memory writes."""

from __future__ import annotations

from collections.abc import Callable

from smb_requirement_agent.analysis.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.breakdown.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.breakdown.application.ports.feature_repository import (
    FeatureRepositoryPort,
)
from smb_requirement_agent.breakdown.application.ports.story_repository import StoryRepositoryPort
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.breakdown.domain.epic.value_objects import EpicId
from smb_requirement_agent.breakdown.domain.feature.entities import Feature
from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.breakdown.domain.story.value_objects import StoryId
from smb_requirement_agent.governance.application.ports.breakdown_repository import (
    BreakdownRepositoryPort,
)
from smb_requirement_agent.governance.application.ports.breakdown_review_repository import (
    BreakdownReviewRepositoryPort,
)
from smb_requirement_agent.governance.domain.review.entities import BreakdownReview
from smb_requirement_agent.identity.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.identity.domain.entities import DraftOwnership, RequirementAccess
from smb_requirement_agent.infrastructure.persistence.in_memory_transaction import (
    InMemoryTransactionManager,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class TrackingRequirementRepository(RequirementRepositoryPort):
    def __init__(
        self,
        inner: RequirementRepositoryPort,
        revisions: BreakdownRepositoryPort,
        transactions: InMemoryTransactionManager,
    ) -> None:
        self._inner = inner
        self._revisions = revisions
        self._transactions = transactions

    def add(self, requirement: Requirement) -> None:
        self._inner.add(requirement)
        # Creation is completed by assigning the creator as owner.  That
        # access write checkpoints the single atomic, externally visible
        # state instead of recording a transient unowned revision first.

    def get(self, requirement_id: RequirementId) -> Requirement | None:
        return self._inner.get(requirement_id)

    def list_all(self) -> list[Requirement]:
        return self._inner.list_all()

    def save(self, requirement: Requirement) -> None:
        self._inner.save(requirement)
        self._transactions.checkpoint(requirement.id, self._revisions)


class TrackingAccessRepository(AccessRepositoryPort):
    def __init__(
        self,
        inner: AccessRepositoryPort,
        revisions: BreakdownRepositoryPort,
        transactions: InMemoryTransactionManager,
    ) -> None:
        self._inner = inner
        self._revisions = revisions
        self._transactions = transactions

    def get_requirement(self, requirement_id: RequirementId) -> RequirementAccess | None:
        return self._inner.get_requirement(requirement_id)

    def save_requirement(self, access: RequirementAccess) -> None:
        self._inner.save_requirement(access)
        self._transactions.checkpoint(access.requirement_id, self._revisions)

    def get_draft_ownership(self, draft_id: RequirementId) -> DraftOwnership | None:
        return self._inner.get_draft_ownership(draft_id)

    def save_draft_ownership(self, ownership: DraftOwnership) -> None:
        self._inner.save_draft_ownership(ownership)

    def delete_draft_ownership(self, draft_id: RequirementId) -> None:
        self._inner.delete_draft_ownership(draft_id)


class TrackingAnalysisRepository:
    def __init__(
        self,
        inner: RequirementAnalysisRepositoryPort,
        revisions: BreakdownRepositoryPort,
        transactions: InMemoryTransactionManager,
    ) -> None:
        self._inner = inner
        self._revisions = revisions
        self._transactions = transactions

    def save(self, analysis: RequirementAnalysis) -> None:
        self._inner.save(analysis)
        self._transactions.checkpoint(analysis.requirement_id, self._revisions)

    def get_by_requirement_id(self, requirement_id: RequirementId) -> RequirementAnalysis | None:
        return self._inner.get_by_requirement_id(requirement_id)

    def delete_by_requirement_id(self, requirement_id: RequirementId) -> None:
        self._inner.delete_by_requirement_id(requirement_id)
        self._transactions.checkpoint(requirement_id, self._revisions)


class TrackingEpicRepository:
    def __init__(
        self,
        inner: EpicRepositoryPort,
        revisions: BreakdownRepositoryPort,
        transactions: InMemoryTransactionManager,
    ) -> None:
        self._inner = inner
        self._revisions = revisions
        self._transactions = transactions

    def save(self, epic: Epic) -> None:
        self._inner.save(epic)
        self._transactions.checkpoint(epic.requirement_id, self._revisions)

    def get_by_requirement_id(self, requirement_id: RequirementId) -> Epic | None:
        return self._inner.get_by_requirement_id(requirement_id)

    def delete_by_requirement_id(self, requirement_id: RequirementId) -> None:
        self._inner.delete_by_requirement_id(requirement_id)
        self._transactions.checkpoint(requirement_id, self._revisions)


class TrackingFeatureRepository:
    def __init__(
        self,
        inner: FeatureRepositoryPort,
        requirement_id_for_epic: Callable[[EpicId], RequirementId | None],
        revisions: BreakdownRepositoryPort,
        transactions: InMemoryTransactionManager,
    ) -> None:
        self._inner = inner
        self._requirement_id_for_epic = requirement_id_for_epic
        self._revisions = revisions
        self._transactions = transactions

    def replace_for_epic(
        self, epic_id: EpicId, features: list[Feature], expected_set_version: int
    ) -> int:
        version = self._inner.replace_for_epic(epic_id, features, expected_set_version)
        self._checkpoint(epic_id)
        return version

    def set_version(self, epic_id: EpicId) -> int:
        return self._inner.set_version(epic_id)

    def get_by_epic_id(self, epic_id: EpicId) -> list[Feature]:
        return self._inner.get_by_epic_id(epic_id)

    def get(self, epic_id: EpicId, feature_id: FeatureId) -> Feature | None:
        return self._inner.get(epic_id, feature_id)

    def save(self, feature: Feature) -> None:
        self._inner.save(feature)
        self._checkpoint(feature.epic_id)

    def delete_by_epic_id(self, epic_id: EpicId) -> None:
        self._inner.delete_by_epic_id(epic_id)
        self._checkpoint(epic_id)

    def _checkpoint(self, epic_id: EpicId) -> None:
        requirement_id = self._requirement_id_for_epic(epic_id)
        if requirement_id is not None:
            self._transactions.checkpoint(requirement_id, self._revisions)


class TrackingStoryRepository:
    def __init__(
        self,
        inner: StoryRepositoryPort,
        epic_id_for_feature: Callable[[FeatureId], EpicId | None],
        requirement_id_for_epic: Callable[[EpicId], RequirementId | None],
        revisions: BreakdownRepositoryPort,
        transactions: InMemoryTransactionManager,
    ) -> None:
        self._inner = inner
        self._epic_id_for_feature = epic_id_for_feature
        self._requirement_id_for_epic = requirement_id_for_epic
        self._revisions = revisions
        self._transactions = transactions

    def replace_for_feature(
        self, feature_id: FeatureId, stories: list[UserStory], expected_set_version: int
    ) -> int:
        version = self._inner.replace_for_feature(feature_id, stories, expected_set_version)
        self._checkpoint(feature_id)
        return version

    def set_version(self, feature_id: FeatureId) -> int:
        return self._inner.set_version(feature_id)

    def get_by_feature_id(self, feature_id: FeatureId) -> list[UserStory]:
        return self._inner.get_by_feature_id(feature_id)

    def get(self, feature_id: FeatureId, story_id: StoryId) -> UserStory | None:
        return self._inner.get(feature_id, story_id)

    def save(self, story: UserStory) -> None:
        self._inner.save(story)
        self._checkpoint(story.feature_id)

    def _checkpoint(self, feature_id: FeatureId) -> None:
        epic_id = self._epic_id_for_feature(feature_id)
        if epic_id is None:
            return
        requirement_id = self._requirement_id_for_epic(epic_id)
        if requirement_id is not None:
            self._transactions.checkpoint(requirement_id, self._revisions)


class TrackingBreakdownReviewRepository:
    def __init__(
        self,
        inner: BreakdownReviewRepositoryPort,
        revisions: BreakdownRepositoryPort,
        transactions: InMemoryTransactionManager,
    ) -> None:
        self._inner = inner
        self._revisions = revisions
        self._transactions = transactions

    def get(self, requirement_id: RequirementId) -> BreakdownReview | None:
        return self._inner.get(requirement_id)

    def save(self, review: BreakdownReview) -> None:
        self._inner.save(review)
        self._transactions.checkpoint(review.requirement_id, self._revisions)
