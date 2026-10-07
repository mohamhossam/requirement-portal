"""Semantic INVEST evaluation boundary."""

from typing import Protocol

from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.domain.story.quality import (
    InvestCriterion,
    StoryQualityEvidence,
    ValidationFinding,
)

# MIGRATION SHIM: StoryQualityEvidence lives in domain/story/quality.py since ADR-0103 PR 6.
# The import-rewrite commit points its importers there and drops this re-export.
__all__ = ["EMPTY_QUALITY_EVIDENCE", "StoryQualityEvaluatorPort", "StoryQualityEvidence"]


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
