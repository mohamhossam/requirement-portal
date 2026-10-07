"""Deterministic semantic INVEST evaluator for offline mode and tests."""

from __future__ import annotations

from collections.abc import Mapping

from smb_requirement_agent.application.ports.story_quality_evaluator import EMPTY_QUALITY_EVIDENCE
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.domain.story.quality import (
    FindingSource,
    InvestCriterion,
    StoryQualityEvidence,
    ValidationFinding,
)

FAKE_QUALITY_MODEL = "fake"
FAKE_QUALITY_PROMPT_VERSION = "fake-story-quality-v1"


class FakeStoryQualityEvaluator:
    model = FAKE_QUALITY_MODEL
    prompt_version = FAKE_QUALITY_PROMPT_VERSION

    def __init__(self, results: Mapping[InvestCriterion, tuple[bool, str]]) -> None:
        self._results = dict(results)

    @classmethod
    def passing(cls) -> FakeStoryQualityEvaluator:
        return cls(
            {
                criterion: (True, f"The Story provides usable {criterion.value} evidence.")
                for criterion in InvestCriterion
                if criterion is not InvestCriterion.TESTABLE
            }
        )

    def evaluate(
        self,
        story: UserStory,
        siblings: tuple[UserStory, ...],
        criteria: tuple[InvestCriterion, ...],
        *,
        evidence: StoryQualityEvidence = EMPTY_QUALITY_EVIDENCE,
    ) -> tuple[ValidationFinding, ...]:
        del story, siblings
        return tuple(
            ValidationFinding(
                criterion,
                self._results[criterion][0],
                self._results[criterion][1],
                FindingSource.SEMANTIC,
            )
            for criterion in criteria
        )
