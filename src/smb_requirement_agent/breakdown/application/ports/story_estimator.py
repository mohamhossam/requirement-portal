"""AI boundary for suggesting relative Story sizes (ADR-0121)."""

from typing import Protocol

from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.breakdown.domain.story.estimate import EstimateSuggestion
from smb_requirement_agent.breakdown.domain.story.quality import StoryQualityEvidence


class StoryEstimatorPort(Protocol):
    model: str
    prompt_version: str

    def suggest(
        self, stories: tuple[UserStory, ...], *, evidence: StoryQualityEvidence
    ) -> tuple[EstimateSuggestion, ...]:
        """One suggestion per Story, sized relative to the others in the set."""
        ...
