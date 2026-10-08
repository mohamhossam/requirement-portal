"""The Requirement corpus and its findings, row by row, for the Knowledge Center (B2).

What leaves requirement work is identity and state: a Requirement's id, title and status, its
owner's display name (never an email, the ADR-0101 rule), when it was last screened and how
its index stands, and for a finding its kind, age, both Requirements and the judge's one-line
rationale. Never a description, a passage or an evidence excerpt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol


class IndexState(StrEnum):
    CURRENT = "current"
    WAITING = "waiting"
    FAILED = "failed"
    # The embedding model changed; every Requirement waits for the rebuild.
    REBUILD_REQUIRED = "rebuild_required"


class FindingAge(StrEnum):
    UNDER_7_DAYS = "under_7_days"
    FROM_7_TO_30_DAYS = "from_7_to_30_days"
    OVER_30_DAYS = "over_30_days"


def finding_age(age: timedelta) -> FindingAge:
    """The corpus summary's buckets: under 7 days, 7 to 30 days inclusive, over 30 days."""
    if age < timedelta(days=7):
        return FindingAge.UNDER_7_DAYS
    return FindingAge.FROM_7_TO_30_DAYS if age <= timedelta(days=30) else FindingAge.OVER_30_DAYS


@dataclass(frozen=True)
class PersonName:
    """Someone named in a row: an id and a display name, never an email."""

    id: str
    display_name: str


@dataclass(frozen=True)
class RetiredMark:
    """A Requirement retired from the corpus: when, by which knowledge admin, and why."""

    at: datetime
    by: str
    reason: str


@dataclass(frozen=True)
class CorpusEntry:
    """One Requirement as the adapter reads it; its index state is decided by the use case."""

    requirement_id: str
    title: str
    duplicate: bool
    owner: PersonName | None
    last_screened_at: datetime | None
    open_findings: int
    retired: RetiredMark | None = None


@dataclass(frozen=True)
class CorpusQuery:
    owner_id: str | None = None
    # Matched against titles, ignoring case.
    text: str = ""
    open_findings_only: bool = False
    # Never screened, or last screened before this moment.
    not_screened_since: datetime | None = None
    # Restricts the rows to these Requirements, or keeps them out (index-state filters).
    only: frozenset[str] | None = None
    excluding: frozenset[str] = frozenset()
    # Only Requirements retired from the corpus (B3).
    retired_only: bool = False


@dataclass(frozen=True)
class FindingSide:
    requirement_id: str
    title: str
    owner: PersonName | None


@dataclass(frozen=True)
class NudgeMark:
    at: datetime
    by: str


@dataclass(frozen=True)
class FindingEntry:
    finding_id: str
    kind: str
    rationale: str
    raised_at: datetime
    subject: FindingSide
    related: FindingSide
    last_nudge: NudgeMark | None


@dataclass(frozen=True)
class FindingQuery:
    # Ages are measured to this moment.
    now: datetime
    kind: str | None = None
    age: FindingAge | None = None
    # Either Requirement's owner.
    owner_id: str | None = None


class KnowledgePortfolioPort(Protocol):
    def corpus(self, query: CorpusQuery, offset: int, limit: int) -> tuple[CorpusEntry, ...]:
        """Requirements by title, then id; a finding counts while it is in force."""
        ...

    def findings(self, query: FindingQuery, offset: int, limit: int) -> tuple[FindingEntry, ...]:
        """Findings in force, the longest-standing first."""
        ...


@dataclass(frozen=True)
class FindingNudge:
    nudge_id: str
    finding_id: str
    actor_id: str
    actor_name: str
    nudged_at: datetime
    recipients: tuple[str, ...]


class FindingNudgesPort(Protocol):
    def latest(self, finding_id: str) -> FindingNudge | None: ...

    def add(self, nudge: FindingNudge) -> None: ...
