"""Suggest Story sizes with the AI, and record the size the team confirms (ADR-0121)."""

from __future__ import annotations

from dataclasses import dataclass

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.application.ports.domain_events import DomainEventPublisher
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.breakdown.application.errors import (
    StoryEstimateSuggestionsConflictError,
    StoryEstimateSuggestionsNotFoundError,
)
from smb_requirement_agent.breakdown.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.breakdown.application.ports.feature_repository import (
    FeatureRepositoryPort,
)
from smb_requirement_agent.breakdown.application.ports.story_estimate_repository import (
    StoryEstimateSuggestionRepositoryPort,
)
from smb_requirement_agent.breakdown.application.ports.story_estimator import StoryEstimatorPort
from smb_requirement_agent.breakdown.application.ports.story_repository import (
    StoryRepositoryPort,
)
from smb_requirement_agent.breakdown.application.published import story_set_fingerprint
from smb_requirement_agent.breakdown.application.use_cases.story_workflow import (
    GetStories,
    StoryWorkflow,
    atomic_story_change,
)
from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.breakdown.domain.story.estimate import (
    EstimateBasis,
    FeatureEstimateSuggestions,
    StoryEstimate,
    StoryPoints,
)
from smb_requirement_agent.breakdown.domain.story.events import StoriesChanged
from smb_requirement_agent.breakdown.domain.story.quality import StoryQualityEvidence
from smb_requirement_agent.breakdown.domain.story.value_objects import StoryId
from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementAccessPort,
    RequirementPermission,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True)
class EstimateSuggestionsView:
    suggestions: FeatureEstimateSuggestions
    fresh: bool


@dataclass(frozen=True)
class StoryEstimateInput:
    """The size a person chose; `points=None` clears it."""

    points: int | None
    basis: EstimateBasis = EstimateBasis.TEAM_ENTERED
    expected_version: int = 1


class SuggestStoryEstimates:
    """Size a Feature's Stories together, relative to each other, as one AI pass."""

    def __init__(
        self,
        get_stories: GetStories,
        estimator: StoryEstimatorPort,
        repository: StoryEstimateSuggestionRepositoryPort,
        transactions: TransactionManagerPort,
        clock: ClockPort,
        *,
        authorization: RequirementAccessPort,
    ) -> None:
        self._authorization = authorization
        self._get_stories = get_stories
        self._estimator = estimator
        self._repository = repository
        self._transactions = transactions
        self._clock = clock

    def execute(
        self, actor: ActorProfile, requirement_id: RequirementId, feature_id: FeatureId
    ) -> EstimateSuggestionsView:
        return self._authorization.execute_mutation(
            requirement_id,
            actor,
            RequirementPermission.MEMBER,
            lambda: self._execute(requirement_id=requirement_id, feature_id=feature_id),
        )

    def _execute(
        self, requirement_id: RequirementId, feature_id: FeatureId
    ) -> EstimateSuggestionsView:
        stories = tuple(self._get_stories.execute(requirement_id, feature_id))
        if not stories:
            raise StoryEstimateSuggestionsConflictError("This Feature has no Stories to size.")
        evidence = self._get_stories.quality_evidence(requirement_id, feature_id)
        fingerprint = story_set_fingerprint(stories, evidence)
        existing = self._repository.get(feature_id)
        if existing is not None and existing.source_fingerprint == fingerprint:
            return EstimateSuggestionsView(existing, True)
        with self._transactions.external_call():
            suggested = self._estimator.suggest(stories, evidence=evidence)
        suggestions = FeatureEstimateSuggestions(
            feature_id,
            fingerprint,
            suggested,
            Provenance(self._clock.now(), self._estimator.model, self._estimator.prompt_version),
        )
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            current = tuple(self._get_stories.execute(requirement_id, feature_id))
            if (
                story_set_fingerprint(
                    current, self._get_stories.quality_evidence(requirement_id, feature_id)
                )
                != fingerprint
            ):
                raise StoryEstimateSuggestionsConflictError(
                    "Stories changed while sizes were suggested. Suggest sizes again."
                )
            self._repository.save(suggestions)
        return EstimateSuggestionsView(suggestions, True)


class GetStoryEstimateSuggestions:
    def __init__(
        self, get_stories: GetStories, repository: StoryEstimateSuggestionRepositoryPort
    ) -> None:
        self._get_stories = get_stories
        self._repository = repository

    def execute(
        self, requirement_id: RequirementId, feature_id: FeatureId
    ) -> EstimateSuggestionsView:
        current = tuple(self._get_stories.execute(requirement_id, feature_id))
        suggestions = self._repository.get(feature_id)
        if suggestions is None:
            raise StoryEstimateSuggestionsNotFoundError(
                f"Feature {feature_id.value!r} has no saved size suggestions."
            )
        evidence = self._get_stories.quality_evidence(requirement_id, feature_id)
        return EstimateSuggestionsView(
            suggestions, suggestions.source_fingerprint == story_set_fingerprint(current, evidence)
        )


class SetStoryEstimate(StoryWorkflow):
    """Record, change or clear the size a person decided on."""

    def __init__(
        self,
        requirement_repository: RequirementRepositoryPort,
        analysis_repository: RequirementAnalysisRepositoryPort,
        epic_repository: EpicRepositoryPort,
        feature_repository: FeatureRepositoryPort,
        story_repository: StoryRepositoryPort,
        transaction_manager: TransactionManagerPort,
        events: DomainEventPublisher,
        *,
        authorization: RequirementAccessPort,
        suggestions: StoryEstimateSuggestionRepositoryPort,
        clock: ClockPort,
    ) -> None:
        super().__init__(
            requirement_repository,
            analysis_repository,
            epic_repository,
            feature_repository,
            story_repository,
            transaction_manager,
            events,
            authorization=authorization,
        )
        self._suggestions = suggestions
        self._clock = clock

    def execute(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        story_id: StoryId,
        data: StoryEstimateInput,
    ) -> UserStory:
        with self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER):
            return self._execute(
                requirement_id=requirement_id,
                feature_id=feature_id,
                story_id=story_id,
                data=data,
                actor=actor,
            )

    @atomic_story_change
    def _execute(
        self,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        story_id: StoryId,
        data: StoryEstimateInput,
        actor: ActorProfile,
    ) -> UserStory:
        context = self._context(requirement_id, feature_id)
        self._ensure_ready(context.feature)
        story = self._story(feature_id, story_id)
        if story.version != data.expected_version:
            raise ArtifactVersionConflictError(
                f"Story changed from version {data.expected_version} to {story.version}. Reload it."
            )
        estimate = None
        if data.points is not None:
            points = StoryPoints(data.points)
            if data.basis is EstimateBasis.ACCEPTED_SUGGESTION:
                evidence = StoryQualityEvidence.from_context(
                    context.requirement, context.analysis, context.feature
                )
                self._require_current_suggestion(feature_id, story_id, points, evidence)
            estimate = StoryEstimate(points, data.basis, actor.snapshot(), self._clock.now())
        sized = story.sized(estimate)
        if sized is story:
            return story
        self._stories.save(sized)
        self._events.publish(StoriesChanged(requirement_id=requirement_id, feature_id=feature_id))
        return sized

    def _require_current_suggestion(
        self,
        feature_id: FeatureId,
        story_id: StoryId,
        points: StoryPoints,
        evidence: StoryQualityEvidence,
    ) -> None:
        """An accepted suggestion must be one the AI actually made for this content."""
        suggestions = self._suggestions.get(feature_id)
        current = tuple(self._stories.get_by_feature_id(feature_id))
        suggestion = suggestions.for_story(story_id) if suggestions else None
        if (
            suggestions is None
            or suggestions.source_fingerprint != story_set_fingerprint(current, evidence)
            or suggestion is None
            or suggestion.points != points
        ):
            raise StoryEstimateSuggestionsConflictError(
                "That size is not the current suggestion for this Story. Reload it."
            )
