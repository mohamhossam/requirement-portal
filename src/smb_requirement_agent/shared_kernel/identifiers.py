"""Identities every context refers to (ADR-0103 Amendment 1)."""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.shared_kernel.errors import InvalidRequirementIdError


@dataclass(frozen=True)
class RequirementId:
    """Identifies a Requirement within the system."""

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped:
            raise InvalidRequirementIdError("Requirement id must not be blank.")
        object.__setattr__(self, "value", stripped)
