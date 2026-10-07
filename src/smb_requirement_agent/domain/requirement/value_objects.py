"""Value objects for the Requirement aggregate."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from smb_requirement_agent.domain.requirement.errors import (
    InvalidRequirementContextError,
    InvalidRequirementDescriptionError,
    InvalidRequirementTitleError,
    InvalidRequirementVersionError,
)


@dataclass(frozen=True)
class RequirementTitle:
    """A non-empty, non-blank title for a Requirement.

    Surrounding whitespace is normalised on construction.
    """

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped:
            raise InvalidRequirementTitleError(
                "Requirement title must not be empty or consist only of whitespace."
            )
        object.__setattr__(self, "value", stripped)


@dataclass(frozen=True)
class RequirementDescription:
    """Typed business need; validated attachment sources may have no typed text.

    Surrounding whitespace is normalised on construction.
    """

    value: str
    attachment_backed: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped and not self.attachment_backed:
            raise InvalidRequirementDescriptionError(
                "Requirement description must not be empty or consist only of whitespace."
            )
        object.__setattr__(self, "value", stripped)


@dataclass(frozen=True)
class RequirementContext:
    """A non-blank structured intake value."""

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped:
            raise InvalidRequirementContextError("Requirement context values must not be blank.")
        object.__setattr__(self, "value", stripped)


@dataclass(frozen=True)
class RequirementVersion:
    """Optimistic concurrency version for editable source content."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 1:
            raise InvalidRequirementVersionError("Requirement version must be at least 1.")

    def next(self) -> RequirementVersion:
        return RequirementVersion(self.value + 1)


class RequirementStatus(Enum):
    """Lifecycle status of a Requirement."""

    DRAFT = "draft"
    DUPLICATE = "duplicate"
