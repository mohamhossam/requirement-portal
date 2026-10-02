"""Sample requirements a maintainer checks every new catalogue version against."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

from smb_requirement_agent.domain.architecture.knowledge import InvalidKnowledgeError

MAX_SAMPLES = 20
MAX_SAMPLE_CHARACTERS = 2_000


@dataclass(frozen=True)
class SampleRequirement:
    id: str
    text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", self.text.strip())
        if not self.id.strip():
            raise InvalidKnowledgeError("A sample requirement needs an id.")
        if not self.text:
            raise InvalidKnowledgeError("A sample requirement must not be blank.")
        if len(self.text) > MAX_SAMPLE_CHARACTERS:
            raise InvalidKnowledgeError(
                f"A sample requirement is at most {MAX_SAMPLE_CHARACTERS:,} characters."
            )


@dataclass(frozen=True)
class SampleRequirementSet:
    """The team's shared list. Replaced as a whole under a revision check."""

    revision: int = 0
    items: tuple[SampleRequirement, ...] = field(default_factory=tuple)
    updated_by: str | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.revision < 0:
            raise InvalidKnowledgeError("Invalid sample list revision.")
        if len(self.items) > MAX_SAMPLES:
            raise InvalidKnowledgeError(f"Keep at most {MAX_SAMPLES} sample requirements.")
        if len({item.id for item in self.items}) != len(self.items):
            raise InvalidKnowledgeError("Sample requirement ids must be unique.")

    def replaced(
        self, items: tuple[SampleRequirement, ...], actor_id: str, at: datetime
    ) -> SampleRequirementSet:
        return replace(
            self, revision=self.revision + 1, items=items, updated_by=actor_id, updated_at=at
        )
