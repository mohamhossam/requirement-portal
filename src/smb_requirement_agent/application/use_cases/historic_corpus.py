"""Requirement work's historic corpus: projected from events, read in pages, indexed.

The knowledge portal announces each publication of a historic requirement as an event
(ADR-0102). Requirement work projects those events with its own cursor, reads each
publication's content a page at a time, and indexes it as a historic corpus apart from
the live one. Only a publication read and embedded in full becomes searchable; a
withdrawal stops it being searchable in the same transaction that records it.
"""

from __future__ import annotations

import hashlib
import math
from datetime import timedelta

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    KnowledgeGenerationError,
    ModelTransportError,
    ServiceUnavailableError,
)
from smb_requirement_agent.application.ports.embedding import KnowledgeEmbeddingPort
from smb_requirement_agent.application.ports.historic_corpus import (
    CONTENT_PAGE_MAX,
    ContentPart,
    HistoricChunk,
    HistoricContentGoneError,
    HistoricContentSourcePort,
    HistoricCorpusIndexPort,
    HistoricRequirementStatePort,
)
from smb_requirement_agent.application.ports.knowledge_events import (
    HISTORIC_REQUIREMENT_CHANGED,
    KnowledgeEventSourcePort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.knowledge_event_cursor import contiguous_reach
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    bounded_knowledge_text,
)
from smb_requirement_agent.domain.knowledge.errors import InvalidKnowledgeError
from smb_requirement_agent.domain.knowledge.historic import (
    HistoricPassage,
    HistoricRequirementState,
    HistoricSourceKind,
    HistoricWorkItem,
    ancestors,
)

# Bounds on what one historic requirement adds to the corpus. Reaching one is not an error:
# the rest of the record is still searchable.
SPANS_PER_ENTRY = 8
CHUNKS_PER_RECORD = 20_000
EMBED_BATCH = 16
# Part of the index identity: a change to how chunks are cut re-indexes the corpus.
HISTORIC_CHUNKER = "historic-chunks-v1"


def historic_identity(embedding_identity: str) -> str:
    return f"{embedding_identity}|{HISTORIC_CHUNKER}"


class ProjectHistoricRequirements:
    """Bring the historic copy up to date with the knowledge portal's events.

    It has its own cursor, from 0, so publications made before requirement work read
    historic events are not missed (ADR-0102). Other kinds of event are stepped over.
    """

    def __init__(
        self,
        outbox: KnowledgeEventSourcePort,
        states: HistoricRequirementStatePort,
        index: HistoricCorpusIndexPort,
        transactions: TransactionManagerPort,
        clock: ClockPort,
        batch: int = 100,
        gap_grace: timedelta = timedelta(seconds=60),
    ) -> None:
        self._outbox = outbox
        self._states = states
        self._index = index
        self._transactions = transactions
        self._clock = clock
        self._batch = batch
        self._gap_grace = gap_grace

    def project_next(self) -> bool:
        cursor = self._states.cursor()
        # Read outside the transaction: nothing is held while the knowledge portal answers.
        events = self._outbox.after(cursor, self._batch)
        with self._transactions.transaction():
            if self._states.cursor() != cursor:
                return True  # Another worker moved on meanwhile; read again from there.
            for event in events:
                if event.kind != HISTORIC_REQUIREMENT_CHANGED:
                    continue
                state = HistoricRequirementState.from_payload(event.payload)
                if self._states.apply(event.seq, state) and state.published is None:
                    self._index.remove(state.historic_requirement_id)
            reached = contiguous_reach(cursor, events, self._clock.now(), self._gap_grace)
            if reached > cursor:
                self._states.advance(reached)
            return reached > cursor

    def drain(self) -> None:
        """Project until caught up, or until the cursor waits at an in-flight gap."""
        for _ in range(1000):
            if not self.project_next():
                return


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _spans(text: str) -> tuple[str, ...]:
    return tuple(span for span in bounded_knowledge_text(text) if span.strip())[:SPANS_PER_ENTRY]


def historic_chunks(
    historic_id: str, staged: dict[ContentPart, tuple[object, ...]]
) -> tuple[HistoricChunk, ...]:
    """A publication's passages and work items as chunks, each with what a reader is shown.

    A passage keeps its BRD and location; a work item keeps its lineage, Epic first.
    """
    chunks: list[HistoricChunk] = []

    def add(kind: HistoricSourceKind, field: str, text: str, evidence: dict[str, object]) -> None:
        for number, span in enumerate(_spans(text)):
            if len(chunks) >= CHUNKS_PER_RECORD:
                return
            text_hash = _digest(span)
            chunk_id = _digest(f"{historic_id}:{kind}:{field}:{number}:{text_hash}")
            chunks.append(
                HistoricChunk(chunk_id, historic_id, kind, field, span, text_hash, evidence)
            )

    for entry in staged.get(ContentPart.PASSAGES, ()):
        passage = HistoricPassage.from_entry(entry)
        if passage.text:
            add(
                HistoricSourceKind.HISTORIC_BRD,
                f"brd:{passage.brd_id}:{passage.block_id}",
                passage.text,
                {
                    "brd_filename": passage.filename,
                    "label": passage.label,
                    "section_path": list(passage.section_path),
                },
            )
    items = {
        item.id: item
        for item in (
            HistoricWorkItem.from_entry(entry) for entry in staged.get(ContentPart.ITEMS, ())
        )
    }
    for item in items.values():
        lines = [f"{item.type_label} #{item.id} {item.title}"]
        if item.description:
            lines.append(item.description)
        if item.acceptance_criteria:
            lines.append(f"Acceptance criteria: {item.acceptance_criteria}")
        add(
            HistoricSourceKind.HISTORIC_BACKLOG,
            f"item:{item.id}",
            "\n".join(lines),
            {
                "lineage": [
                    {
                        "id": link.id,
                        "type": link.type,
                        "title": link.title,
                        "state": link.state,
                        "url": link.url,
                    }
                    for link in ancestors(items, item.id)
                ]
            },
        )
    return tuple(chunks)


def _usable(vector: tuple[float, ...]) -> bool:
    return len(vector) == 768 and all(math.isfinite(x) for x in vector) and any(vector)


class IndexHistoricCorpus:
    """One step of indexing a publication each call: a page read, chunks cut, or a batch
    embedded. Its chunks become searchable together, once every one has a vector."""

    def __init__(
        self,
        content: HistoricContentSourcePort,
        index: HistoricCorpusIndexPort,
        embeddings: KnowledgeEmbeddingPort,
        clock: ClockPort,
        identity: str,
        embed_per_hour: int,
    ) -> None:
        self._content = content
        self._index = index
        self._embeddings = embeddings
        self._clock = clock
        self.identity = identity
        self._embed_per_hour = embed_per_hour

    def process_next(self) -> bool:
        now = self._clock.now()
        pending = self._index.next_pending(self.identity, now)
        if pending is None:
            return False
        historic_id, seq = pending.historic_id, pending.seq
        try:
            if pending.part is not None:
                page = self._content.page(
                    historic_id, pending.publication, pending.part, pending.offset, CONTENT_PAGE_MAX
                )
                if (
                    page.publication != pending.publication
                    or page.fingerprint != pending.fingerprint
                ):
                    raise HistoricContentGoneError("The content read is not the announced one.")
                if page.next_offset is not None:
                    following: tuple[ContentPart | None, int] = (pending.part, page.next_offset)
                elif pending.part is ContentPart.PASSAGES:
                    following = (ContentPart.ITEMS, 0)
                else:
                    following = (None, 0)
                self._index.save_page(pending, pending.part, page.entries, *following)
                return True
            if not pending.chunks_built:
                chunks = historic_chunks(historic_id, self._index.staged(historic_id, seq))
                self._index.stage_chunks(historic_id, seq, self.identity, chunks)
                return True
            allowed = self._index.embedding_budget(historic_id, now, self._embed_per_hour)
            batch = self._index.unembedded(
                historic_id, seq, self.identity, max(0, min(EMBED_BATCH, allowed))
            )
            if batch:
                vectors = self._embeddings.embed(tuple(chunk.text for chunk in batch))
                if len(vectors) != len(batch) or not all(_usable(v) for v in vectors):
                    raise KnowledgeGenerationError("Embedding provider returned incomplete batch.")
                self._index.save_vectors(
                    historic_id,
                    seq,
                    self.identity,
                    {chunk.chunk_id: vector for chunk, vector in zip(batch, vectors, strict=True)},
                )
                self._index.spend_embedding_budget(historic_id, now, len(batch))
                return True
            if allowed <= 0 and self._index.unembedded(historic_id, seq, self.identity, 1):
                # This hour's budget for the record is spent; the rest waits for the next hour.
                self._index.defer(
                    historic_id, now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                )
                return True
            self._index.complete(historic_id, seq, self.identity)
            return True
        except HistoricContentGoneError:
            # A newer publication or a withdrawal is on its way; read whatever it says instead.
            self._index.restart(historic_id, seq)
            self._index.defer(historic_id, now + timedelta(seconds=30))
            return True
        except (
            KnowledgeGenerationError,
            ModelTransportError,
            ServiceUnavailableError,
            InvalidKnowledgeError,
        ):
            self._index.record_failure(
                historic_id, now + timedelta(seconds=30 * 2 ** min(pending.failures, 10))
            )
            return True
