"""Map the current Feature and Story tree to reviewable architecture impact."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.errors import (
    ArchitectureMappingConflictError,
    ArtifactVersionConflictError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.domain_events import DomainEventPublisher
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.breakdown.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.breakdown.application.ports.feature_repository import (
    FeatureRepositoryPort,
)
from smb_requirement_agent.breakdown.application.ports.story_repository import StoryRepositoryPort
from smb_requirement_agent.breakdown.domain.architecture.entities import ArchitectureImpact
from smb_requirement_agent.breakdown.domain.architecture.events import ArchitectureImpactChanged
from smb_requirement_agent.breakdown.domain.feature.entities import Feature
from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementAccessPort,
    RequirementPermission,
)
from smb_requirement_agent.references.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureKnowledgePort,
    ArchitectureQuery,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


def _unfenced() -> None:
    """A direct request holds no job lease, so there is nothing to renew."""


@dataclass(frozen=True)
class StoryArchitectureMapping:
    story: UserStory
    impact: ArchitectureImpact


@dataclass(frozen=True)
class FeatureArchitectureMapping:
    feature: Feature
    impact: ArchitectureImpact
    stories: tuple[StoryArchitectureMapping, ...]


@dataclass(frozen=True)
class BreakdownArchitectureMapping:
    requirement_id: RequirementId
    features: tuple[FeatureArchitectureMapping, ...]


def _impact(match: ArchitectureKnowledgeMatch, mapped_at: datetime) -> ArchitectureImpact:
    return ArchitectureImpact(
        match.knowledge_version,
        mapped_at,
        match.systems,
        match.dependencies,
        match.citation_ids,
        match.uncertainty,
        match.model,
        match.embedding_model,
        match.prompt_version,
        match.index_revision,
        match.evidence_classification,
        match.citations,
        match.adjacent_systems,
        match.adjacent_dependencies,
        match.adjacent_omitted,
        match.suggested_domains,
        match.product_contexts,
        match.journey_steps,
    )


class MapFeatureArchitecture:
    def __init__(self, knowledge: ArchitectureKnowledgePort) -> None:
        self._knowledge = knowledge

    def execute(
        self,
        requirement: Requirement,
        feature: Feature,
        mapped_at: datetime,
        release_id: str | None = None,
    ) -> FeatureArchitectureMapping:
        match = self._knowledge.match(
            ArchitectureQuery(
                text=(
                    feature.name.value,
                    feature.outcome.value,
                    feature.splitting_rationale.value,
                ),
                declared_systems=tuple(item.value for item in requirement.systems),
                release_id=release_id,
            )
        )
        impact = _impact(match, mapped_at)
        return FeatureArchitectureMapping(feature.with_architecture(impact), impact, ())


class MapStoryArchitecture:
    def __init__(self, knowledge: ArchitectureKnowledgePort) -> None:
        self._knowledge = knowledge

    def execute(
        self,
        requirement: Requirement,
        feature: Feature,
        story: UserStory,
        mapped_at: datetime,
        release_id: str | None = None,
    ) -> StoryArchitectureMapping:
        criteria = tuple(
            part
            for item in story.acceptance_criteria
            for part in (item.given, item.when, item.then)
        )
        match = self._knowledge.match(
            ArchitectureQuery(
                text=(
                    feature.name.value,
                    feature.outcome.value,
                    story.voice,
                    *criteria,
                ),
                declared_systems=tuple(item.value for item in requirement.systems),
                release_id=release_id,
            )
        )
        impact = _impact(match, mapped_at)
        return StoryArchitectureMapping(story.with_architecture(impact), impact)


class MapBreakdownArchitecture:
    """Map and persist the complete current breakdown in one application action."""

    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        analyses: RequirementAnalysisRepositoryPort,
        epics: EpicRepositoryPort,
        features: FeatureRepositoryPort,
        stories: StoryRepositoryPort,
        transaction_manager: TransactionManagerPort,
        feature_mapper: MapFeatureArchitecture,
        story_mapper: MapStoryArchitecture,
        clock: ClockPort,
        events: DomainEventPublisher,
        *,
        authorization: RequirementAccessPort,
    ) -> None:
        self._authorization = authorization
        self._requirements = requirements
        self._analyses = analyses
        self._epics = epics
        self._features = features
        self._stories = stories
        self._transactions = transaction_manager
        self._feature_mapper = feature_mapper
        self._story_mapper = story_mapper
        self._clock = clock
        self._events = events

    def authorize(self, actor: ActorProfile, requirement_id: RequirementId) -> None:
        """Refuse to accept mapping work for a Requirement the actor cannot change."""
        self._authorization.require_requirement_member(requirement_id, actor)

    def input_fingerprint(self, requirement_id: RequirementId) -> str:
        requirement = self._requirements.get(requirement_id)
        analysis = self._analyses.get_by_requirement_id(requirement_id)
        epic = self._epics.get_by_requirement_id(requirement_id)
        features = self._features.get_by_epic_id(epic.id) if epic else []
        stories = tuple(
            (feature.id, self._stories.get_by_feature_id(feature.id)) for feature in features
        )
        content = repr((requirement, analysis, epic, features, stories))
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def execute(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        *,
        release_id: str | None = None,
        expected_fingerprint: str | None = None,
        fence: Callable[[], None] = _unfenced,
    ) -> BreakdownArchitectureMapping:
        """Map and save the breakdown's architecture.

        `fence` runs inside the commit transaction before anything is saved. A
        background job passes one that renews its lease, so an attempt that lost
        its lease cannot write; a direct request has no lease to hold.
        """
        return self._authorization.execute_mutation(
            requirement_id,
            actor,
            RequirementPermission.MEMBER,
            lambda: self._execute(
                requirement_id=requirement_id,
                release_id=release_id,
                expected_fingerprint=expected_fingerprint,
                fence=fence,
            ),
        )

    def _execute(
        self,
        requirement_id: RequirementId,
        *,
        release_id: str | None,
        expected_fingerprint: str | None,
        fence: Callable[[], None],
    ) -> BreakdownArchitectureMapping:
        if expected_fingerprint is not None and (
            self.input_fingerprint(requirement_id) != expected_fingerprint
        ):
            raise ArtifactVersionConflictError(
                "The breakdown changed before architecture mapping started. Reload it."
            )
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        analysis = self._analyses.get_by_requirement_id(requirement_id)
        if analysis is None or not analysis.is_human_confirmed:
            raise ArchitectureMappingConflictError(
                "Architecture mapping requires a current, human-confirmed analysis."
            )
        epic = self._epics.get_by_requirement_id(requirement_id)
        if epic is None or epic.is_stale:
            raise ArchitectureMappingConflictError(
                "Architecture mapping requires a current Epic and Feature breakdown."
            )
        features = self._features.get_by_epic_id(epic.id)
        if not features:
            raise ArchitectureMappingConflictError(
                "Architecture mapping requires at least one current Feature."
            )
        stories_by_feature = {
            feature.id: self._stories.get_by_feature_id(feature.id) for feature in features
        }
        if any(feature.is_stale for feature in features) or any(
            story.is_stale for stories in stories_by_feature.values() for story in stories
        ):
            raise ArchitectureMappingConflictError(
                "Reconcile stale Features and Stories before mapping architecture."
            )

        mapped_at = self._clock.now()
        mappings: list[FeatureArchitectureMapping] = []
        pinned_release = release_id
        for feature in features:
            feature_mapping = self._feature_mapper.execute(
                requirement, feature, mapped_at, pinned_release
            )
            pinned_release = feature_mapping.impact.knowledge_version
            story_mappings = tuple(
                self._story_mapper.execute(requirement, feature, story, mapped_at, pinned_release)
                for story in stories_by_feature[feature.id]
            )
            mappings.append(
                FeatureArchitectureMapping(
                    feature_mapping.feature,
                    feature_mapping.impact,
                    story_mappings,
                )
            )

        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            fence()
            if (
                (
                    expected_fingerprint is not None
                    and self.input_fingerprint(requirement_id) != expected_fingerprint
                )
                or self._requirements.get(requirement_id) != requirement
                or self._analyses.get_by_requirement_id(requirement_id) != analysis
                or self._epics.get_by_requirement_id(requirement_id) != epic
                or self._features.get_by_epic_id(epic.id) != features
                or any(
                    self._stories.get_by_feature_id(feature.id) != stories_by_feature[feature.id]
                    for feature in features
                )
            ):
                raise ArtifactVersionConflictError(
                    "The breakdown changed while architecture was mapped. Reload it."
                )
            for mapping in mappings:
                self._features.save(mapping.feature)
                for story_mapping in mapping.stories:
                    self._stories.save(story_mapping.story)
            self._events.publish(ArchitectureImpactChanged(requirement_id=requirement_id))

        return BreakdownArchitectureMapping(requirement_id, tuple(mappings))
