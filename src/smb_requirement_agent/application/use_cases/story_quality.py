"""Validate Story INVEST quality and map failures to SPIDR strategies."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    StoryNotFoundError,
    StoryQualitySnapshotConflictError,
    StoryQualitySnapshotNotFoundError,
)
from smb_requirement_agent.application.ports.story_quality_evaluator import (
    StoryQualityEvaluatorPort,
    StoryQualityEvidence,
)
from smb_requirement_agent.application.ports.story_quality_repository import (
    StoryQualityRepositoryPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementAccessService,
    RequirementPermission,
)

if TYPE_CHECKING:
    from smb_requirement_agent.application.use_cases.story_workflow import GetStories
from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.shared.actors import ActorProfile
from smb_requirement_agent.domain.shared.generation import Provenance
from smb_requirement_agent.domain.shared.identifiers import RequirementId
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.domain.story.quality import (
    FeatureQualitySnapshot,
    FindingSource,
    InvestAssessment,
    InvestCriterion,
    SpidrPattern,
    SpidrRecommendation,
    ValidationFinding,
)
from smb_requirement_agent.domain.story.value_objects import StoryId

SEMANTIC_CRITERIA = (
    InvestCriterion.INDEPENDENT,
    InvestCriterion.NEGOTIABLE,
    InvestCriterion.VALUABLE,
    InvestCriterion.ESTIMABLE,
    InvestCriterion.SMALL,
)


class AssessStoryCandidate:
    """Assess an unsaved candidate against its projected siblings."""

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


class ValidateStory(AssessStoryCandidate):
    def __init__(
        self,
        get_stories: GetStories,
        evaluator: StoryQualityEvaluatorPort,
        clock: ClockPort,
    ) -> None:
        super().__init__(evaluator, clock)
        self._get_stories = get_stories

    def execute(
        self, requirement_id: RequirementId, feature_id: FeatureId, story_id: StoryId
    ) -> InvestAssessment:
        stories = tuple(self._get_stories.execute(requirement_id, feature_id))
        story = next((item for item in stories if item.id == story_id), None)
        if story is None:
            raise StoryNotFoundError(
                f"No Story {story_id.value!r} under Feature {feature_id.value!r}."
            )
        return self.assess(
            story, stories, self._get_stories.quality_evidence(requirement_id, feature_id)
        )


class ValidateFeatureStories:
    def __init__(self, get_stories: GetStories, validator: ValidateStory) -> None:
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
        authorization: RequirementAccessService,
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


def story_set_fingerprint(stories: tuple[UserStory, ...], evidence: StoryQualityEvidence) -> str:
    payload = [
        {
            "id": story.id.value,
            "voice": story.voice,
            "criteria": [
                [criterion.given, criterion.when, criterion.then]
                for criterion in story.acceptance_criteria
            ],
        }
        for story in stories
    ]
    canonical = json.dumps(
        {"stories": payload, "evidence": asdict(evidence)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SuggestStorySplit:
    def __init__(self, validator: ValidateStory) -> None:
        self._validator = validator

    def execute(
        self, requirement_id: RequirementId, feature_id: FeatureId, story_id: StoryId
    ) -> tuple[SpidrRecommendation, ...]:
        return self.for_assessment(self._validator.execute(requirement_id, feature_id, story_id))

    @staticmethod
    def for_assessment(
        assessment: InvestAssessment,
    ) -> tuple[SpidrRecommendation, ...]:
        failed = {finding.criterion for finding in assessment.findings if not finding.passed}
        recommendations: list[SpidrRecommendation] = []
        if InvestCriterion.ESTIMABLE in failed:
            recommendations.append(
                SpidrRecommendation(
                    SpidrPattern.SPIKE,
                    "Time-box the unresolved delivery uncertainty, then split with the evidence.",
                )
            )
        if InvestCriterion.INDEPENDENT in failed:
            recommendations.append(
                SpidrRecommendation(
                    SpidrPattern.INTERFACES,
                    "Separate the interface or integration boundary to reduce coupling.",
                )
            )
        if InvestCriterion.SMALL in failed:
            recommendations.append(
                SpidrRecommendation(
                    SpidrPattern.PATHS,
                    "Deliver the primary path first and sequence alternatives as "
                    "follow-on Stories.",
                )
            )
        if InvestCriterion.TESTABLE in failed:
            recommendations.append(
                SpidrRecommendation(
                    SpidrPattern.DATA,
                    "Split by a concrete data example so each outcome can be verified.",
                )
            )
        if {InvestCriterion.NEGOTIABLE, InvestCriterion.VALUABLE} & failed:
            recommendations.append(
                SpidrRecommendation(
                    SpidrPattern.RULES,
                    "Isolate one business rule and its value so scope remains negotiable.",
                )
            )
        return tuple(dict.fromkeys(recommendations))
