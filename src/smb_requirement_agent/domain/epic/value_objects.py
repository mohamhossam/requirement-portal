"""Value objects for the Epic aggregate.

Status, provenance and staleness are shared with every other generated
aggregate and are re-exported here under their Epic-facing names, so callers
inside this package read consistently.
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.domain.epic.errors import InvalidEpicContentError
from smb_requirement_agent.shared_kernel.generation import GenerationStatus, Provenance
from smb_requirement_agent.shared_kernel.staleness import Staleness, StaleReason

EpicStatus = GenerationStatus
EpicProvenance = Provenance
EpicStaleness = Staleness

__all__ = [
    "BusinessCase",
    "BusinessOutcome",
    "EpicId",
    "EpicName",
    "EpicProvenance",
    "EpicStaleness",
    "EpicStatus",
    "StaleReason",
]


def _normalised(value: str, field: str) -> str:
    """Strip surrounding whitespace, rejecting empty and blank input."""
    stripped = value.strip()
    if not stripped:
        raise InvalidEpicContentError(f"Epic {field} must not be empty or blank.")
    return stripped


@dataclass(frozen=True)
class EpicId:
    """Identifies an Epic within the system."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalised(self.value, "id"))


@dataclass(frozen=True)
class EpicName:
    """The Epic's name."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalised(self.value, "name"))


@dataclass(frozen=True)
class BusinessOutcome:
    """The measurable business outcome the Epic delivers."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalised(self.value, "outcome"))


@dataclass(frozen=True)
class BusinessCase:
    """The justification for the Epic, in one or two sentences."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalised(self.value, "business case"))
