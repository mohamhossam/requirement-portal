"""Epic repository port."""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class EpicRepositoryPort(Protocol):
    """Outbound port for persisting Epics.

    Keyed by requirement while the one-Epic-per-requirement rule holds.
    """

    def save(self, epic: Epic) -> None:
        """Save a new or updated Epic."""
        ...

    def get_by_requirement_id(self, requirement_id: RequirementId) -> Epic | None:
        """Retrieve the Epic for a requirement, or None."""
        ...

    def delete_by_requirement_id(self, requirement_id: RequirementId) -> None:
        """Delete the Epic for a requirement, if one exists."""
        ...
