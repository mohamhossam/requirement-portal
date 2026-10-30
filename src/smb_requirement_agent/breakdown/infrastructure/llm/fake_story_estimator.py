"""Deterministic Story size estimator for offline mode and tests."""

from __future__ import annotations

from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.breakdown.domain.story.estimate import (
    EstimateSuggestion,
    StoryPoints,
)
from smb_requirement_agent.breakdown.domain.story.quality import StoryQualityEvidence

FAKE_ESTIMATE_MODEL = "fake"
FAKE_ESTIMATE_PROMPT_VERSION = "fake-story-estimate-v1"

# Acceptance-criteria count -> size. Stable, so offline journeys are repeatable.
_SIZES = {1: 2, 2: 3, 3: 5, 4: 8, 5: 8}


class FakeStoryEstimator:
    model = FAKE_ESTIMATE_MODEL
    prompt_version = FAKE_ESTIMATE_PROMPT_VERSION

    def suggest(
        self, stories: tuple[UserStory, ...], *, evidence: StoryQualityEvidence
    ) -> tuple[EstimateSuggestion, ...]:
        del evidence
        return tuple(self._suggest(story) for story in stories)

    @staticmethod
    def _suggest(story: UserStory) -> EstimateSuggestion:
        count = len(story.acceptance_criteria)
        criteria = f"{count} acceptance criteri{'on' if count == 1 else 'a'}"
        points = _SIZES.get(count)
        if points is None:
            return EstimateSuggestion(
                story.id,
                None,
                f"{criteria} describe more than one sprint of work; split it before sizing.",
            )
        return EstimateSuggestion(
            story.id,
            StoryPoints(points),
            f"{criteria}, sized relative to the other Stories in the Feature.",
        )
