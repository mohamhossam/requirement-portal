"""Prepare and refine unsaved backlog candidates before the owning mutation commits."""

from collections.abc import Callable
from dataclasses import dataclass, replace

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import FeatureGenerationError, StoryGenerationError
from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgePort,
    ArchitectureQuery,
)
from smb_requirement_agent.application.ports.candidate_review import CandidateReviewPort
from smb_requirement_agent.application.ports.generation_guidance import GenerationGuidance
from smb_requirement_agent.application.ports.requirement_evidence_analyzer import (
    AnalysisProgressPort,
)
from smb_requirement_agent.application.ports.story_quality_repository import (
    StoryQualityRepositoryPort,
)
from smb_requirement_agent.application.use_cases.architecture_mapping import (
    MapFeatureArchitecture,
    MapStoryArchitecture,
)
from smb_requirement_agent.application.use_cases.story_quality import (
    AssessStoryCandidate,
    SuggestStorySplit,
    story_set_fingerprint,
)
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.domain.story.quality import (
    FeatureQualitySnapshot,
    InvestCriterion,
    StoryQualityEvidence,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True)
class PreparedStories:
    stories: tuple[UserStory, ...]
    snapshot: FeatureQualitySnapshot


class GenerationChecks:
    def __init__(
        self,
        knowledge: ArchitectureKnowledgePort,
        feature_mapper: MapFeatureArchitecture,
        story_mapper: MapStoryArchitecture,
        assessor: AssessStoryCandidate,
        quality: StoryQualityRepositoryPort,
        review: CandidateReviewPort,
        clock: ClockPort,
        progress: AnalysisProgressPort,
    ) -> None:
        self._knowledge = knowledge
        self._feature_mapper = feature_mapper
        self._story_mapper = story_mapper
        self._assessor = assessor
        self._quality = quality
        self._review = review
        self._clock = clock
        self._progress = progress

    def _phase(self, requirement_id: RequirementId, phase: str, step: int) -> None:
        self._progress.report(requirement_id, phase, step, 5, None)

    def guidance(
        self, requirement: Requirement, analysis: RequirementAnalysis
    ) -> GenerationGuidance:
        self._phase(requirement.id, "preparing", 0)
        return GenerationGuidance(
            architecture=self._knowledge.match(
                ArchitectureQuery(
                    text=(
                        requirement.title.value,
                        requirement.description.value,
                        *(item.statement for item in analysis.known_facts),
                        *(item.statement for item in analysis.constraints),
                        *analysis.accepted_constraints,
                    ),
                    declared_systems=tuple(item.value for item in requirement.systems),
                )
            ),
            potential_dependencies=tuple(
                item.statement for item in analysis.potential_dependencies
            ),
            ambiguities=tuple(item.statement for item in analysis.ambiguities),
        )

    def features(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        generate: Callable[[GenerationGuidance], list[Feature]],
    ) -> list[Feature]:
        guidance = self.guidance(requirement, analysis)
        for attempt in range(2):
            self._phase(
                requirement.id, "generating" if attempt == 0 else "refining", 1 + attempt * 2
            )
            candidates = generate(guidance)
            if not candidates:
                raise FeatureGenerationError("Provider returned no usable Feature candidates.")
            self._phase(requirement.id, "checking", 2 + attempt * 2)
            candidates = [
                self._feature_mapper.execute(requirement, item, self._clock.now()).feature
                for item in candidates
            ]
            critique = self._review.critique_features(requirement, analysis, tuple(candidates))
            if attempt == 1 or not critique.has_flags:
                break
            guidance = replace(
                guidance,
                feedback=critique.feedback,
                previous_draft=tuple(
                    f"{item.name.value}: {item.outcome.value}; {item.delivery_drop.value}; "
                    f"{item.splitting_pattern.value}: {item.splitting_rationale.value}"
                    for item in candidates
                ),
            )
        self._phase(requirement.id, "saving", 5)
        return candidates

    def stories(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        feature: Feature,
        generate: Callable[[GenerationGuidance], list[UserStory]],
        project: Callable[[list[UserStory]], list[UserStory]],
        *,
        allow_split: bool,
    ) -> PreparedStories:
        guidance = self.guidance(requirement, analysis)
        evidence = StoryQualityEvidence.from_context(requirement, analysis, feature)
        for attempt in range(2):
            self._phase(
                requirement.id, "generating" if attempt == 0 else "refining", 1 + attempt * 2
            )
            candidates = generate(guidance)
            if not candidates:
                raise StoryGenerationError("Provider returned no usable Story candidates.")
            if len(candidates) < guidance.minimum_story_count:
                raise StoryGenerationError(
                    "Story refinement ignored the required split: expected at least "
                    f"{guidance.minimum_story_count} Stories. The previous saved result "
                    "has been preserved."
                )
            self._phase(requirement.id, "checking", 2 + attempt * 2)
            candidates = [
                self._story_mapper.execute(requirement, feature, item, self._clock.now()).story
                for item in candidates
            ]
            siblings = tuple(project(candidates))
            assessments = tuple(
                self._assessor.assess(item, siblings, evidence) for item in siblings
            )
            candidate_ids = {item.id for item in candidates}
            feedback = tuple(
                f"{story.voice} — {finding.criterion.value}: {finding.message}"
                for story in candidates
                for assessment in assessments
                if assessment.story_id == story.id
                for finding in assessment.findings
                if not finding.passed
            )
            if attempt == 1 or not feedback:
                break
            guidance = replace(
                guidance,
                minimum_story_count=(
                    2
                    if allow_split
                    and len(candidates) == 1
                    and any(
                        assessment.failure_count >= 2
                        and any(
                            finding.criterion is InvestCriterion.SMALL and not finding.passed
                            for finding in assessment.findings
                        )
                        for assessment in assessments
                        if assessment.story_id in candidate_ids
                    )
                    else 1
                ),
                feedback=feedback
                + tuple(
                    f"{item.pattern.value}: {item.reason}"
                    for assessment in assessments
                    if assessment.story_id in candidate_ids
                    for item in SuggestStorySplit.for_assessment(assessment)
                ),
                previous_draft=tuple(
                    story.voice
                    + "\n"
                    + "\n".join(
                        f"Given {ac.given}; When {ac.when}; Then {ac.then}"
                        for ac in story.acceptance_criteria
                    )
                    for story in candidates
                ),
            )
        self._phase(requirement.id, "saving", 5)
        return PreparedStories(
            siblings,
            FeatureQualitySnapshot(
                feature.id,
                story_set_fingerprint(siblings, evidence),
                assessments,
                self._clock.now(),
            ),
        )

    def save(self, requirement_id: RequirementId, snapshot: FeatureQualitySnapshot | None) -> None:
        """Called inside the owning artifact transaction, after storing its final content."""
        if snapshot is not None:
            self._quality.save(snapshot)
        self._review.refresh(requirement_id)
