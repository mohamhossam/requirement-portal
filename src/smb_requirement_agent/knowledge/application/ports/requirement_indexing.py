"""Durable, fenced progress for bounded Requirement embedding batches."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from smb_requirement_agent.knowledge.application.ports.requirement_knowledge import Embedding

# A source stops retrying after this many failed batches, until someone retries it.
FAILED_AFTER = 3


@dataclass(frozen=True)
class RequirementIndexProgress:
    source_change: int = 0
    failures: int = 0
    retry_at: datetime | None = None
    vectors: tuple[tuple[str, Embedding], ...] = ()
    completed: int = 0
    total: int = 0


class RequirementIndexProgressPort(Protocol):
    def get(self, identity: str, source: str) -> RequirementIndexProgress: ...

    def claim(
        self,
        identity: str,
        source: str,
        change: int,
        token: str,
        now: datetime,
        until: datetime,
    ) -> RequirementIndexProgress | None: ...

    def save(
        self,
        identity: str,
        source: str,
        token: str,
        progress: RequirementIndexProgress,
        now: datetime,
    ) -> bool: ...

    def retry(self, identity: str, source: str, now: datetime) -> bool: ...

    def failed(self, identity: str) -> tuple[tuple[str, int], ...]:
        """Each source that has stopped retrying, with the source change it failed on."""
        ...
