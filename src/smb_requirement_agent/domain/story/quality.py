"""INVEST quality findings and documented Story split recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.story.errors import InvalidStoryContentError
from smb_requirement_agent.domain.story.value_objects import StoryId
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.staleness import require_aware


class InvestCriterion(Enum):
    INDEPENDENT = "independent"
    NEGOTIABLE = "negotiable"
    VALUABLE = "valuable"
    ESTIMABLE = "estimable"
    SMALL = "small"
    TESTABLE = "testable"


class FindingSource(Enum):
    DETERMINISTIC = "deterministic"
    SEMANTIC = "semantic"


class StoryQualityStatus(Enum):
    PASSES = "passes"
    NEEDS_ATTENTION = "needs_attention"
    SPLIT_RECOMMENDED = "split_recommended"


class SpidrPattern(Enum):
    SPIKE = "spike"
    PATHS = "paths"
    INTERFACES = "interfaces"
    DATA = "data"
    RULES = "rules"


@dataclass(frozen=True)
class ValidationFinding:
    criterion: InvestCriterion
    passed: bool
    message: str
    source: FindingSource

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise InvalidStoryContentError("An INVEST finding must explain its result.")
        object.__setattr__(self, "message", self.message.strip())


@dataclass(frozen=True)
class InvestAssessment:
    story_id: StoryId
    findings: tuple[ValidationFinding, ...]
    provenance: Provenance

    def __post_init__(self) -> None:
        criteria = [finding.criterion for finding in self.findings]
        if set(criteria) != set(InvestCriterion) or len(criteria) != len(InvestCriterion):
            raise InvalidStoryContentError(
                "An INVEST assessment must contain exactly one finding for every criterion."
            )

    @property
    def failure_count(self) -> int:
        return sum(not finding.passed for finding in self.findings)

    @property
    def status(self) -> StoryQualityStatus:
        if self.failure_count == 0:
            return StoryQualityStatus.PASSES
        if self.failure_count == 1:
            return StoryQualityStatus.NEEDS_ATTENTION
        return StoryQualityStatus.SPLIT_RECOMMENDED


@dataclass(frozen=True)
class SpidrRecommendation:
    pattern: SpidrPattern
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise InvalidStoryContentError("A SPIDR recommendation must explain its reason.")
        object.__setattr__(self, "reason", self.reason.strip())


@dataclass(frozen=True)
class FeatureQualitySnapshot:
    feature_id: FeatureId
    source_fingerprint: str
    assessments: tuple[InvestAssessment, ...]
    generated_at: datetime

    def __post_init__(self) -> None:
        if not self.source_fingerprint.strip():
            raise InvalidStoryContentError("Quality source fingerprint must not be blank.")
        require_aware(self.generated_at, "quality generated_at")


@dataclass(frozen=True)
class StoryQualityEvidence:
    source_facts: tuple[str, ...] = ()
    human_decisions: tuple[str, ...] = ()
    unconfirmed: tuple[str, ...] = ()
    feature_boundary: tuple[str, ...] = ()

    @classmethod
    def from_context(
        cls, requirement: Requirement, analysis: RequirementAnalysis, feature: Feature
    ) -> StoryQualityEvidence:
        return cls(
            source_facts=(
                requirement.title.value,
                requirement.description.value,
                *(item.value for item in requirement.business_rules),
                *(item.value for item in requirement.constraints),
                *(f"Declared channel: {item.value}" for item in requirement.channels),
                *(f"Declared system: {item.value}" for item in requirement.systems),
                *((requirement.desired_outcome.value,) if requirement.desired_outcome else ()),
                *((requirement.customer_context.value,) if requirement.customer_context else ()),
                *(item.statement for item in analysis.known_facts),
                *(item.statement for item in analysis.constraints),
                *(item.statement for item in analysis.business_rules),
            ),
            human_decisions=(
                *(f"{item.subject}: {item.answer}" for item in analysis.clarifications),
                *analysis.accepted_constraints,
                *analysis.accepted_business_rules,
                analysis.effective_desired_outcome() or "No confirmed desired outcome supplied.",
            ),
            unconfirmed=(
                *(item.statement for item in analysis.assumptions),
                *(item.question for item in analysis.open_questions),
                *(item.statement for item in analysis.ambiguities),
                *(item.statement for item in analysis.potential_dependencies),
            ),
            feature_boundary=(feature.name.value, feature.outcome.value),
        )


def spidr_recommendations(assessment: InvestAssessment) -> tuple[SpidrRecommendation, ...]:
    """The documented SPIDR split for each failed INVEST criterion, in a fixed order."""
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
                "Deliver the primary path first and sequence alternatives as follow-on Stories.",
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
