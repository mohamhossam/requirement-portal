"""INVEST quality findings and documented Story split recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.shared.generation import Provenance
from smb_requirement_agent.domain.shared.staleness import require_aware
from smb_requirement_agent.domain.story.errors import InvalidStoryContentError
from smb_requirement_agent.domain.story.value_objects import StoryId


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
