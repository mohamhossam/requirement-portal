"""Finding which catalogue system a name from a document may refer to."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SystemMatchingError(Exception):
    """The matching model produced nothing usable; the provider is at fault."""


@dataclass(frozen=True)
class MatchQuery:
    """A system name as the document writes it, with the passage it appears in."""

    written_as: str
    context: str


@dataclass(frozen=True)
class MatchableSystem:
    id: str
    name: str
    name_ar: str | None
    aliases: tuple[str, ...]
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class MatchSuggestion:
    written_as: str
    system_id: str
    reason: str


@dataclass(frozen=True)
class MatchResult:
    suggestions: tuple[MatchSuggestion, ...]
    warnings: tuple[str, ...] = ()


class SystemMatcherPort(Protocol):
    @property
    def model(self) -> str: ...

    @property
    def prompt_version(self) -> str: ...

    def match(
        self, queries: tuple[MatchQuery, ...], systems: tuple[MatchableSystem, ...]
    ) -> MatchResult:
        """Existing systems each query may name, never one outside ``systems``.

        Raises SystemMatchingError when the model's answer cannot be used.
        """
        ...
