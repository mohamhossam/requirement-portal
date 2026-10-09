"""How governance has a Story assessed against INVEST while it reviews a breakdown.

Governance owns this port; the composition root fills it with breakdown's `AssessStoryCandidate`
(ADR-0103 Amendment 3), so governance never imports another context's use case.
"""

from typing import Protocol

from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.breakdown.domain.story.quality import (
    InvestAssessment,
    StoryQualityEvidence,
)


class StoryAssessmentPort(Protocol):
    def assess(
        self, story: UserStory, siblings: tuple[UserStory, ...], evidence: StoryQualityEvidence
    ) -> InvestAssessment: ...
