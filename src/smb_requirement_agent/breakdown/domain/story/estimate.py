"""Story point sizes: an AI suggestion, and the team's decision (ADR-0121).

A suggestion is AI output a person reviews. It is kept beside the Stories, goes out of
date when their content changes, and never reaches a revision or an export. A size
becomes part of the Story only when a person confirms it, and only then counts.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.errors import InvalidStoryContentError
from smb_requirement_agent.breakdown.domain.story.value_objects import StoryId
from smb_requirement_agent.shared_kernel.actors import ActorSnapshot
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.staleness import require_aware

# The relative sizing scale. Anything bigger than 13 is a Story to split, not to size.
STORY_POINT_SCALE: tuple[int, ...] = (1, 2, 3, 5, 8, 13)


@dataclass(frozen=True, order=True)
class StoryPoints:
    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or self.value not in STORY_POINT_SCALE:
            scale = ", ".join(str(item) for item in STORY_POINT_SCALE)
            raise InvalidStoryContentError(f"Story points must be one of {scale}.")


class EstimateBasis(Enum):
    """Where a confirmed size came from, so provenance stays honest."""

    ACCEPTED_SUGGESTION = "accepted_suggestion"
    TEAM_ENTERED = "team_entered"


@dataclass(frozen=True)
class StoryEstimate:
    """A size a person decided on, and who decided it."""

    points: StoryPoints
    basis: EstimateBasis
    decided_by: ActorSnapshot
    decided_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.decided_at, "estimate decided_at")


@dataclass(frozen=True)
class EstimateSuggestion:
    """The AI's size for one Story, or its honest reason for not giving one.

    No size is a legitimate answer: a Story that rests on an unmade business decision, or
    is too big for the scale, is reported rather than guessed at.
    """

    story_id: StoryId
    points: StoryPoints | None
    rationale: str

    def __post_init__(self) -> None:
        if not self.rationale.strip():
            raise InvalidStoryContentError("A size suggestion must explain its reasoning.")
        object.__setattr__(self, "rationale", self.rationale.strip())


@dataclass(frozen=True)
class FeatureEstimateSuggestions:
    """One sizing pass over a Feature's Stories, bound to the content it read."""

    feature_id: FeatureId
    source_fingerprint: str
    suggestions: tuple[EstimateSuggestion, ...]
    provenance: Provenance

    def __post_init__(self) -> None:
        if not self.source_fingerprint.strip():
            raise InvalidStoryContentError("Size suggestion source fingerprint must not be blank.")
        ids = [item.story_id for item in self.suggestions]
        if not ids or len(set(ids)) != len(ids):
            raise InvalidStoryContentError(
                "Size suggestions need exactly one entry for each Story."
            )

    def for_story(self, story_id: StoryId) -> EstimateSuggestion | None:
        return next((item for item in self.suggestions if item.story_id == story_id), None)


@dataclass(frozen=True)
class EstimateTotal:
    """Confirmed points across a set of Stories, and how many of them are sized."""

    points: int
    sized: int
    stories: int

    @property
    def unsized(self) -> int:
        return self.stories - self.sized


def estimate_total(estimates: Iterable[StoryEstimate | None]) -> EstimateTotal:
    """Only confirmed sizes count; an unsized Story is reported, never treated as zero."""
    items = tuple(estimates)
    sized = tuple(item for item in items if item is not None)
    return EstimateTotal(
        points=sum(item.points.value for item in sized),
        sized=len(sized),
        stories=len(items),
    )
