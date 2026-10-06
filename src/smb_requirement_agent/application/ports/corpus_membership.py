"""Corpus membership and the corpus actions' audit trail (Knowledge Center B3)."""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.domain.knowledge.membership import CorpusAction, CorpusMembership
from smb_requirement_agent.domain.requirement.value_objects import RequirementId


class CorpusMembershipPort(Protocol):
    def get(self, requirement_id: RequirementId) -> CorpusMembership | None:
        """The last corpus action on the Requirement; None when no admin has acted on it."""
        ...

    def retired(self) -> dict[str, CorpusMembership]:
        """Every Requirement retired now, by id."""
        ...

    def save(self, membership: CorpusMembership) -> None:
        """Record a retirement or a reinstatement; the Requirement is then indexed again."""
        ...


class CorpusActionsPort(Protocol):
    def add(self, action: CorpusAction) -> None: ...


class SourceChangesPort(Protocol):
    def mark_changed(self, requirement_ids: tuple[RequirementId, ...]) -> int:
        """Mark these Requirements for indexing again; how many exist to mark."""
        ...
