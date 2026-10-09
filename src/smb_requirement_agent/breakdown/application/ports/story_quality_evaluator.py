"""Semantic INVEST evaluation boundary."""

from typing import Protocol

from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.breakdown.domain.story.quality import (
    InvestCriterion,
    StoryQualityEvidence,
    ValidationFinding,
)

EMPTY_QUALITY_EVIDENCE = StoryQualityEvidence()


class StoryQualityEvaluatorPort(Protocol):
    model: str
    prompt_version: str

    def evaluate(
        self,
        story: UserStory,
        siblings: tuple[UserStory, ...],
        criteria: tuple[InvestCriterion, ...],
        *,
        evidence: StoryQualityEvidence = EMPTY_QUALITY_EVIDENCE,
    ) -> tuple[ValidationFinding, ...]: ...
