"""Validate Story INVEST quality and map failures to SPIDR strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.breakdown.application.errors import (
    StoryQualitySnapshotConflictError,
    StoryQualitySnapshotNotFoundError,
)
from smb_requirement_agent.breakdown.application.ports.story_quality_evaluator import (
    StoryQualityEvaluatorPort,
)
from smb_requirement_agent.breakdown.application.ports.story_quality_repository import (
    StoryQualityRepositoryPort,
)
from smb_requirement_agent.breakdown.application.published import story_set_fingerprint
from smb_requirement_agent.breakdown.domain.story.quality import StoryQualityEvidence
from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementAccessPort,
    RequirementPermission,
)

if TYPE_CHECKING:
    from smb_requirement_agent.breakdown.application.use_cases.story_workflow import GetStories
from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.breakdown.domain.story.quality import (
    FeatureQualitySnapshot,
    FindingSource,
    InvestAssessment,
    InvestCriterion,
    SpidrRecommendation,
    ValidationFinding,
    spidr_recommendations,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

SEMANTIC_CRITERIA = (
    InvestCriterion.INDEPENDENT,
    InvestCriterion.NEGOTIABLE,
    InvestCriterion.VALUABLE,
    InvestCriterion.ESTIMABLE,
    InvestCriterion.SMALL,
)


class AssessStoryCandidate:
    """Assess a Story, saved or a candidate, against its (projected) siblings."""

    def __init__(self, evaluator: StoryQualityEvaluatorPort, clock: ClockPort) -> None:
        self._evaluator = evaluator
        self._clock = clock

    def assess(
        self, story: UserStory, siblings: tuple[UserStory, ...], evidence: StoryQualityEvidence
    ) -> InvestAssessment:
        semantic = self._evaluator.evaluate(story, siblings, SEMANTIC_CRITERIA, evidence=evidence)
        testable = ValidationFinding(
            InvestCriterion.TESTABLE,
            bool(story.acceptance_criteria),
            (
                "At least one complete Given/When/Then criterion is present."
                if story.acceptance_criteria
                else "Add a complete Given/When/Then criterion."
            ),
            FindingSource.DETERMINISTIC,
        )
        return InvestAssessment(
            story.id,
            (*semantic, testable),
            Provenance(self._clock.now(), self._evaluator.model, self._evaluator.prompt_version),
        )


class ValidateFeatureStories:
    def __init__(self, get_stories: GetStories, validator: AssessStoryCandidate) -> None:
        self._get_stories = get_stories
        self._validator = validator

    def execute(
        self, requirement_id: RequirementId, feature_id: FeatureId
    ) -> tuple[InvestAssessment, ...]:
        stories = tuple(self._get_stories.execute(requirement_id, feature_id))
        evidence = self._get_stories.quality_evidence(requirement_id, feature_id)
        return tuple(self._validator.assess(story, stories, evidence) for story in stories)


@dataclass(frozen=True)
class FeatureQualitySnapshotView:
    snapshot: FeatureQualitySnapshot
    fresh: bool


class EvaluateFeatureStories:
    def __init__(
        self,
        get_stories: GetStories,
        validator: ValidateFeatureStories,
        repository: StoryQualityRepositoryPort,
        transactions: TransactionManagerPort,
        clock: ClockPort,
        *,
        authorization: RequirementAccessPort,
    ) -> None:
        self._authorization = authorization
        self._get_stories = get_stories
        self._validator = validator
        self._repository = repository
        self._transactions = transactions
        self._clock = clock

    def execute(
        self, actor: ActorProfile, requirement_id: RequirementId, feature_id: FeatureId
    ) -> FeatureQualitySnapshotView:
        return self._authorization.execute_mutation(
            requirement_id,
            actor,
            RequirementPermission.MEMBER,
            lambda: self._execute(requirement_id=requirement_id, feature_id=feature_id),
        )

    def _execute(
        self, requirement_id: RequirementId, feature_id: FeatureId
    ) -> FeatureQualitySnapshotView:
        stories = tuple(self._get_stories.execute(requirement_id, feature_id))
        fingerprint = story_set_fingerprint(
            stories, self._get_stories.quality_evidence(requirement_id, feature_id)
        )
        existing = self._repository.get(feature_id)
        if existing is not None and existing.source_fingerprint == fingerprint:
            return FeatureQualitySnapshotView(existing, True)
        with self._transactions.external_call():
            assessments = self._validator.execute(requirement_id, feature_id)
        snapshot = FeatureQualitySnapshot(feature_id, fingerprint, assessments, self._clock.now())
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            current = tuple(self._get_stories.execute(requirement_id, feature_id))
            if (
                story_set_fingerprint(
                    current, self._get_stories.quality_evidence(requirement_id, feature_id)
                )
                != fingerprint
            ):
                raise StoryQualitySnapshotConflictError(
                    "Stories changed while quality was evaluated. Start a new quality job."
                )
            self._repository.save(snapshot)
        return FeatureQualitySnapshotView(snapshot, True)


class GetFeatureQualitySnapshot:
    def __init__(
        self,
        get_stories: GetStories,
        repository: StoryQualityRepositoryPort,
    ) -> None:
        self._get_stories = get_stories
        self._repository = repository

    def execute(
        self, requirement_id: RequirementId, feature_id: FeatureId
    ) -> FeatureQualitySnapshotView:
        current = tuple(self._get_stories.execute(requirement_id, feature_id))
        snapshot = self._repository.get(feature_id)
        if snapshot is None:
            raise StoryQualitySnapshotNotFoundError(
                f"Feature {feature_id.value!r} has no saved quality assessment."
            )
        return FeatureQualitySnapshotView(
            snapshot,
            snapshot.source_fingerprint
            == story_set_fingerprint(
                current, self._get_stories.quality_evidence(requirement_id, feature_id)
            ),
        )


class SuggestStorySplit:
    @staticmethod
    def for_assessment(
        assessment: InvestAssessment,
    ) -> tuple[SpidrRecommendation, ...]:
        return spidr_recommendations(assessment)
