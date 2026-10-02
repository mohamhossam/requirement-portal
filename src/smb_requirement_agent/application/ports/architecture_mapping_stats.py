"""How many backlog items are mapped with each architecture catalogue release."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MappingCount:
    release_id: str
    requirements: int
    features: int
    stories: int


class ArchitectureMappingStatsPort(Protocol):
    def by_release(self) -> tuple[MappingCount, ...]:
        """Counts only; never which requirements, so no membership is needed to read them."""
        ...
