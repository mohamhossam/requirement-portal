"""Historic Requirements, as requirement work keeps them (Knowledge Center E2, ADR-0102).

The knowledge portal publishes old BRDs with the Epics, Features and User Stories they were
delivered as in Azure DevOps. Requirement work keeps a local copy, fed by the knowledge
portal's events, and indexes it as a separate historic corpus. It is reference knowledge:
never confirmed intent, never an answer to a clarification, never a finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class HistoricSourceKind(StrEnum):
    """Where a historic chunk comes from. Kept apart from the live corpus's source kinds."""

    HISTORIC_BRD = "historic_brd"
    HISTORIC_BACKLOG = "historic_backlog"


# The trust a historic passage carries: reference, never a requirement's confirmed intent.
REFERENCE_TRUST = "reference"

WORK_ITEM_TYPES = {"epic": "Epic", "feature": "Feature", "user_story": "User Story"}


@dataclass(frozen=True)
class HistoricPublication:
    """What one publication of a historic requirement is, without its content."""

    number: int
    fingerprint: str
    title: str
    published_at: datetime
    published_by: str
    root_ids: tuple[int, ...]


@dataclass(frozen=True)
class HistoricRequirementState:
    """A historic requirement as its latest event left it: published, or withdrawn.

    `version` advances on every change in the knowledge portal. The content of a
    publication is read separately, a page at a time (ADR-0102, amendment 1). Its payload codec
    is infrastructure (`infrastructure/persistence/knowledge_payloads.py`).
    """

    historic_requirement_id: str
    version: int
    published: HistoricPublication | None = None


@dataclass(frozen=True)
class HistoricPassage:
    """One passage of a published BRD, as the knowledge portal read it."""

    brd_id: str
    filename: str
    block_id: str
    label: str
    section_path: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class HistoricWorkItem:
    """An Epic, Feature or User Story a BRD was delivered as, read-only (ADR-0102)."""

    id: int
    type: str
    title: str
    state: str
    url: str | None
    description: str
    acceptance_criteria: str
    area_path: str
    iteration_path: str
    tags: tuple[str, ...]
    parent_id: int | None

    @property
    def type_label(self) -> str:
        return WORK_ITEM_TYPES[self.type]


def safe_url(value: str) -> str | None:
    """Only a web address is kept as a link; anything else is shown without one."""
    url = value.strip()
    return url if url.lower().startswith(("https://", "http://")) else None


def ancestors(items: dict[int, HistoricWorkItem], item_id: int) -> tuple[HistoricWorkItem, ...]:
    """The item's chain from its Epic down to itself, guarded against cycles."""
    chain: list[HistoricWorkItem] = []
    seen: set[int] = set()
    current = items.get(item_id)
    while current is not None and current.id not in seen:
        seen.add(current.id)
        chain.append(current)
        current = None if current.parent_id is None else items.get(current.parent_id)
    return tuple(reversed(chain))
