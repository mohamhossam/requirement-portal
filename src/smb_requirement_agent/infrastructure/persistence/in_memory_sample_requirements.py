"""Process-local sample requirement list for offline development and tests."""

from __future__ import annotations

from threading import RLock

from smb_requirement_agent.domain.architecture.knowledge import KnowledgeConflictError
from smb_requirement_agent.domain.architecture.samples import SampleRequirementSet


class InMemorySampleRequirements:
    def __init__(self) -> None:
        self._lock = RLock()
        self._current = SampleRequirementSet()

    def load(self) -> SampleRequirementSet:
        with self._lock:
            return self._current

    def save(self, updated: SampleRequirementSet, expected_revision: int) -> None:
        with self._lock:
            if self._current.revision != expected_revision:
                raise KnowledgeConflictError("The sample list changed; reload before saving.")
            self._current = updated
