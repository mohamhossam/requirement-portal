"""In-memory evidence fragment cache for offline and test operation."""

from collections.abc import Sequence
from copy import deepcopy
from threading import RLock
from typing import Any

from smb_requirement_agent.analysis.application.ports.requirement_evidence_analyzer import (
    EvidenceFragmentCacheEntry,
    EvidenceFragmentCachePort,
)


class InMemoryEvidenceFragmentCache(EvidenceFragmentCachePort):
    def __init__(self) -> None:
        self._entries: dict[str, EvidenceFragmentCacheEntry] = {}
        self._lock = RLock()

    def snapshot_state(self) -> Any:
        return deepcopy((self._entries,))

    def restore_state(self, state: Any) -> None:
        (self._entries,) = deepcopy(state)

    def get(self, key: str) -> EvidenceFragmentCacheEntry | None:
        with self._lock:
            value = self._entries.get(key)
            return deepcopy(value) if value is not None else None

    def put(self, key: str, value: EvidenceFragmentCacheEntry) -> None:
        self.put_many(((key, value),))

    def put_many(self, values: Sequence[tuple[str, EvidenceFragmentCacheEntry]]) -> None:
        with self._lock:
            replacements = {key: deepcopy(value) for key, value in values}
            self._entries.update(replacements)
