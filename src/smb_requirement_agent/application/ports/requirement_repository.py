"""Outbound port for Requirement persistence.

Application use cases depend only on this abstraction.
Infrastructure adapters implement it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class RequirementRepositoryPort(ABC):
    """Defines the persistence contract for Requirements."""

    @abstractmethod
    def add(self, requirement: Requirement) -> None:
        """Persist a new Requirement.

        Raises DuplicateRequirementError if a Requirement with the same ID exists.
        """

    @abstractmethod
    def get(self, requirement_id: RequirementId) -> Requirement | None:
        """Retrieve a Requirement by ID, or return None if not found."""

    @abstractmethod
    def list_all(self) -> list[Requirement]:
        """Return all Requirements, most recently touched first."""

    @abstractmethod
    def save(self, requirement: Requirement) -> None:
        """Persist updates to an existing Requirement."""
