"""Value objects used by User Stories."""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.domain.story.errors import InvalidStoryContentError


def _non_empty(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise InvalidStoryContentError(f"{field} must not be blank.")
    return cleaned


@dataclass(frozen=True)
class StoryId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _non_empty(self.value, "Story id"))


@dataclass(frozen=True)
class UserRole:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _non_empty(self.value, "User role"))


@dataclass(frozen=True)
class DesiredAction:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _non_empty(self.value, "Desired action"))


@dataclass(frozen=True)
class BusinessValue:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _non_empty(self.value, "Business value"))


@dataclass(frozen=True)
class AcceptanceCriterion:
    given: str
    when: str
    then: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "given", _non_empty(self.given, "Acceptance criterion Given"))
        object.__setattr__(self, "when", _non_empty(self.when, "Acceptance criterion When"))
        object.__setattr__(self, "then", _non_empty(self.then, "Acceptance criterion Then"))


@dataclass(frozen=True)
class StoryProposalId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _non_empty(self.value, "Story proposal id"))
