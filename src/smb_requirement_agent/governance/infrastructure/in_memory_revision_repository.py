"""In-memory append-only revision history for offline development and tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.breakdown.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.breakdown.application.ports.feature_repository import (
    FeatureRepositoryPort,
)
from smb_requirement_agent.breakdown.application.ports.story_repository import StoryRepositoryPort
from smb_requirement_agent.governance.application.ports.breakdown_review_repository import (
    BreakdownReviewRepositoryPort,
)
from smb_requirement_agent.governance.domain.revision.entities import (
    BreakdownRevision,
    RequirementRevision,
    RevisionNumber,
)
from smb_requirement_agent.identity.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class InMemoryRevisionRepository:
    """Captures immutable references to frozen domain aggregates."""

    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        analyses: RequirementAnalysisRepositoryPort,
        epics: EpicRepositoryPort,
        features: FeatureRepositoryPort,
        stories: StoryRepositoryPort,
        reviews: BreakdownReviewRepositoryPort,
        access: AccessRepositoryPort,
        clock: ClockPort,
    ) -> None:
        self._requirements = requirements
        self._analyses = analyses
        self._epics = epics
        self._features = features
        self._stories = stories
        self._reviews = reviews
        self._access = access
        self._clock = clock
        self._requirement_history: dict[str, list[RequirementRevision]] = {}
        self._breakdown_history: dict[str, list[BreakdownRevision]] = {}

    def snapshot_state(self) -> Any:
        return deepcopy(
            (
                self._requirement_history,
                self._breakdown_history,
            )
        )

    def restore_state(self, state: Any) -> None:
        (
            self._requirement_history,
            self._breakdown_history,
        ) = deepcopy(state)

    def create_current_revisions(self, requirement_id: RequirementId) -> None:
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            return
        requirement_history = self._requirement_history.setdefault(requirement_id.value, [])
        access = self._access.get_requirement(requirement_id)
        if (
            not requirement_history
            or requirement_history[-1].requirement != requirement
            or requirement_history[-1].access != access
        ):
            requirement_history.append(
                RequirementRevision(
                    requirement_id,
                    RevisionNumber(len(requirement_history) + 1),
                    self._clock.now(),
                    requirement,
                    access,
                )
            )

        analysis = self._analyses.get_by_requirement_id(requirement_id)
        epic = self._epics.get_by_requirement_id(requirement_id)
        features = tuple(self._features.get_by_epic_id(epic.id)) if epic is not None else ()
        stories = tuple(
            story for feature in features for story in self._stories.get_by_feature_id(feature.id)
        )
        review = self._reviews.get(requirement_id)
        if analysis is None and epic is None and not features and not stories and review is None:
            return
        breakdown_history = self._breakdown_history.setdefault(requirement_id.value, [])
        snapshot = (analysis, epic, features, stories, review)
        previous = breakdown_history[-1] if breakdown_history else None
        if (
            previous is not None
            and (
                previous.analysis,
                previous.epic,
                previous.features,
                previous.stories,
                previous.review,
            )
            == snapshot
        ):
            return
        breakdown_history.append(
            BreakdownRevision(
                requirement_id,
                RevisionNumber(len(breakdown_history) + 1),
                self._clock.now(),
                analysis,
                epic,
                features,
                stories,
                review,
            )
        )

    def list_requirement_revisions(
        self, requirement_id: RequirementId
    ) -> list[RequirementRevision]:
        return list(self._requirement_history.get(requirement_id.value, []))

    def list_breakdown_revisions(self, requirement_id: RequirementId) -> list[BreakdownRevision]:
        return list(self._breakdown_history.get(requirement_id.value, []))

    def get_breakdown_revision(
        self, requirement_id: RequirementId, number: RevisionNumber
    ) -> BreakdownRevision | None:
        history = self._breakdown_history.get(requirement_id.value, [])
        return next((item for item in history if item.number == number), None)
