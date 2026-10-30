"""Turn a sizing response into one usable suggestion per Story, or fail explicitly."""

from __future__ import annotations

from collections.abc import Callable

from smb_requirement_agent.breakdown.application.errors import StoryEstimationError
from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.breakdown.domain.story.estimate import (
    EstimateSuggestion,
    StoryPoints,
)
from smb_requirement_agent.breakdown.infrastructure.llm.schemas.story_estimate_schema import (
    StoryEstimatesSchema,
)

type LabelledStories = tuple[tuple[str, UserStory], ...]
type SizingRequest = Callable[[LabelledStories], StoryEstimatesSchema]


def story_labels(stories: tuple[UserStory, ...]) -> LabelledStories:
    """Short labels keep Story ids out of the prompt and make the reply checkable."""
    return tuple((f"S{index}", story) for index, story in enumerate(stories, start=1))


def _usable(
    response: StoryEstimatesSchema, labelled: dict[str, UserStory]
) -> dict[str, EstimateSuggestion]:
    found: dict[str, EstimateSuggestion] = {}
    for item in response.sizes:
        label = item.story.strip()
        rationale = item.rationale.strip()
        if label not in labelled:
            raise StoryEstimationError(f"The size reply named an unknown Story {label!r}.")
        if label in found:
            raise StoryEstimationError(f"The size reply sized Story {label} twice.")
        if not rationale:
            # A size with no reasoning is not something a person can review: ask again.
            continue
        found[label] = EstimateSuggestion(
            labelled[label].id,
            StoryPoints(item.points) if item.points is not None else None,
            rationale,
        )
    return found


def request_complete_estimates(
    request: SizingRequest, stories: tuple[UserStory, ...]
) -> tuple[EstimateSuggestion, ...]:
    """Ask once for every Story, then once more for any the reply left out."""
    labelled = story_labels(stories)
    found = _usable(request(labelled), dict(labelled))
    missing = tuple((label, story) for label, story in labelled if label not in found)
    if missing:
        found.update(_usable(request(missing), dict(missing)))
    absent = [label for label, _ in labelled if label not in found]
    if absent:
        raise StoryEstimationError(
            f"The size reply left {len(absent)} Story(ies) without a usable size: "
            f"{', '.join(absent)}."
        )
    return tuple(found[label] for label, _ in labelled)
