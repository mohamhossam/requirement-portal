"""Requirement work's copy of historic Requirements and their corpus (ADR-0102).

Three seams: the knowledge portal's paged content read, the local state its events
leave behind, and the historic corpus index built from that content. The historic
corpus is kept apart from the live one: its chunks never key on `requirements`, and
nothing that screens, suggests or answers for live work reads it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from smb_kernel.embeddings import Embedding

from smb_requirement_agent.domain.knowledge.historic import (
    HistoricRequirementState,
    HistoricSourceKind,
)

# The knowledge portal answers at most this many entries a page (ADR-0102, amendment 1).
CONTENT_PAGE_MAX = 200


class ContentPart(StrEnum):
    PASSAGES = "passages"
    ITEMS = "items"


@dataclass(frozen=True)
class HistoricContentPage:
    publication: int
    fingerprint: str
    entries: tuple[object, ...]
    next_offset: int | None


class HistoricContentGoneError(Exception):
    """The publication asked for is no longer the one in use, or the record is withdrawn.

    Not a failure: a newer event says what to read instead.
    """


class HistoricContentSourcePort(Protocol):
    def page(
        self, historic_id: str, publication: int, part: ContentPart, offset: int, limit: int
    ) -> HistoricContentPage: ...


@dataclass(frozen=True)
class HistoricStanding:
    """Whether a historic requirement is published now, and as what."""

    published: bool
    publication: int | None
    title: str


class HistoricRequirementStatePort(Protocol):
    def cursor(self) -> int:
        """The last knowledge event the historic copy has read; its own, from 0."""
        ...

    def advance(self, seq: int) -> None: ...

    def apply(self, seq: int, state: HistoricRequirementState) -> bool:
        """Store `state` unless a newer event for it was already applied; True if stored."""
        ...

    def get(self, historic_id: str) -> HistoricRequirementState | None: ...

    def standing(self, historic_ids: tuple[str, ...]) -> dict[str, HistoricStanding]: ...


@dataclass(frozen=True)
class PendingHistoric:
    """A published record whose searchable chunks are behind its latest publication."""

    historic_id: str
    seq: int
    publication: int
    fingerprint: str
    # How far reading its content has got: the part being read and where, or done.
    part: ContentPart | None
    offset: int
    chunks_built: bool
    failures: int = 0


@dataclass(frozen=True)
class HistoricChunk:
    chunk_id: str
    historic_id: str
    source_kind: HistoricSourceKind
    field: str
    text: str
    text_hash: str
    # What a reader is shown beside the text: the BRD and passage, or the work item's lineage.
    evidence: dict[str, object]


@dataclass(frozen=True)
class HistoricMatch:
    chunk: HistoricChunk
    title: str
    publication: int
    lexical_rank: int | None
    semantic_rank: int | None
    fused_score: float


class HistoricCorpusIndexPort(Protocol):
    def next_pending(self, identity: str, now: datetime) -> PendingHistoric | None: ...

    def save_page(
        self,
        pending: PendingHistoric,
        part: ContentPart,
        entries: tuple[object, ...],
        next_part: ContentPart | None,
        next_offset: int,
    ) -> None:
        """Keep a page of raw content and move the reading on."""
        ...

    def staged(self, historic_id: str, seq: int) -> dict[ContentPart, tuple[object, ...]]: ...

    def stage_chunks(
        self, historic_id: str, seq: int, identity: str, chunks: tuple[HistoricChunk, ...]
    ) -> None:
        """Write the publication's chunks, unsearchable, reusing vectors for unchanged text."""
        ...

    def unembedded(
        self, historic_id: str, seq: int, identity: str, limit: int
    ) -> tuple[HistoricChunk, ...]: ...

    def save_vectors(
        self, historic_id: str, seq: int, identity: str, vectors: dict[str, Embedding]
    ) -> None: ...

    def embedding_budget(self, historic_id: str, now: datetime, hourly: int) -> int:
        """How many chunks of this record may still be embedded this hour."""
        ...

    def spend_embedding_budget(self, historic_id: str, now: datetime, count: int) -> None: ...

    def complete(self, historic_id: str, seq: int, identity: str) -> bool:
        """Make the publication's chunks the searchable ones, unless a newer event arrived."""
        ...

    def restart(self, historic_id: str, seq: int) -> None:
        """Forget what was read for this publication, to read it again from the start."""
        ...

    def record_failure(self, historic_id: str, retry_at: datetime) -> None:
        """Count a failed step and wait until `retry_at` before the next one."""
        ...

    def defer(self, historic_id: str, until: datetime) -> None:
        """Wait until `until` without counting a failure: a budget spent, or a newer event due."""
        ...

    def remove(self, historic_id: str) -> None:
        """Withdrawn: its chunks stop being searchable at once."""
        ...

    def search(
        self, query_text: str, query_embedding: Embedding, identity: str, limit: int
    ) -> tuple[HistoricMatch, ...]: ...

    def version(self) -> int:
        """Advances each time a publication becomes searchable; 0 while none is."""
        ...

    def has_content(self, identity: str) -> bool: ...


class HistoricCorpusPort(HistoricRequirementStatePort, HistoricCorpusIndexPort, Protocol):
    """The copy and its index kept together, so a withdrawal and its removal commit as one."""
