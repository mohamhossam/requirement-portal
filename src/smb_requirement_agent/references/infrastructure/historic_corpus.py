"""Requirement work's historic copy and corpus, in memory and in PostgreSQL (ADR-0102)."""

from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from typing import cast

from psycopg.types.json import Jsonb
from smb_kernel.embeddings import Embedding

from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.references.application.ports.historic_corpus import (
    ContentPart,
    HistoricChunk,
    HistoricMatch,
    HistoricStanding,
    PendingHistoric,
)
from smb_requirement_agent.references.domain.historic import (
    HistoricRequirementState,
    HistoricSourceKind,
)
from smb_requirement_agent.references.infrastructure.knowledge_payloads import (
    historic_requirement_state_from_payload,
    historic_requirement_state_to_payload,
)

_WORDS = re.compile(r"\w+", re.UNICODE)


def _hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def _cosine(left: Embedding, right: Embedding) -> float:
    norm = math.sqrt(sum(x * x for x in left)) * math.sqrt(sum(y * y for y in right))
    return 0.0 if norm == 0 else sum(x * y for x, y in zip(left, right, strict=False)) / norm


def fuse(
    lexical: list[str], semantic: list[str]
) -> dict[str, tuple[int | None, int | None, float]]:
    """Reciprocal rank fusion, k = 60, as the live corpus fuses its two searches."""
    lexical_rank = {chunk_id: rank for rank, chunk_id in enumerate(lexical, 1)}
    semantic_rank = {chunk_id: rank for rank, chunk_id in enumerate(semantic, 1)}
    fused: dict[str, tuple[int | None, int | None, float]] = {}
    for chunk_id in dict.fromkeys([*lexical, *semantic]):
        lex, sem = lexical_rank.get(chunk_id), semantic_rank.get(chunk_id)
        score = (1 / (60 + lex) if lex else 0.0) + (1 / (60 + sem) if sem else 0.0)
        fused[chunk_id] = (lex, sem, score)
    return fused


@dataclass
class _Record:
    seq: int
    state: HistoricRequirementState
    indexed_seq: int | None = None
    indexed_identity: str | None = None
    failures: int = 0
    retry_at: datetime | None = None
    # Reading the publication's content: for which event and model, how far, what was read.
    stage_seq: int | None = None
    stage_identity: str | None = None
    stage_part: ContentPart | None = ContentPart.PASSAGES
    stage_offset: int = 0
    chunks_built: bool = False
    staged: dict[ContentPart, list[object]] = field(default_factory=dict)
    embed_window: datetime | None = None
    embedded: int = 0


@dataclass
class _Row:
    chunk: HistoricChunk
    seq: int
    identity: str
    vector: Embedding | None


class InMemoryHistoricCorpus:
    """Both the historic copy and its corpus index, under the graph-wide lock."""

    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self._records: dict[str, _Record] = {}
        self._rows: dict[tuple[str, int, str, str], _Row] = {}
        self._cursor = 0
        self._version = 0

    def snapshot_state(self) -> object:
        return copy.deepcopy((self._records, self._rows, self._cursor, self._version))

    def restore_state(self, state: object) -> None:
        self._records, self._rows, self._cursor, self._version = cast(
            tuple[dict[str, _Record], dict[tuple[str, int, str, str], _Row], int, int], state
        )

    # --- The copy ------------------------------------------------------------------------

    def cursor(self) -> int:
        with self._lock:
            return self._cursor

    def advance(self, seq: int) -> None:
        with self._lock:
            self._cursor = max(self._cursor, seq)

    def apply(self, seq: int, state: HistoricRequirementState) -> bool:
        with self._lock:
            record = self._records.get(state.historic_requirement_id)
            if record is not None and seq <= record.seq:
                return False
            if record is None:
                self._records[state.historic_requirement_id] = _Record(seq, state)
            else:
                record.seq, record.state = seq, state
                record.failures, record.retry_at = 0, None
            return True

    def get(self, historic_id: str) -> HistoricRequirementState | None:
        with self._lock:
            record = self._records.get(historic_id)
            return None if record is None else record.state

    def standing(self, historic_ids: tuple[str, ...]) -> dict[str, HistoricStanding]:
        with self._lock:
            found: dict[str, HistoricStanding] = {}
            for historic_id in historic_ids:
                record = self._records.get(historic_id)
                if record is None:
                    continue
                published = record.state.published
                found[historic_id] = HistoricStanding(
                    published is not None,
                    None if published is None else published.number,
                    "" if published is None else published.title,
                )
            return found

    # --- The index -----------------------------------------------------------------------

    def next_pending(self, identity: str, now: datetime) -> PendingHistoric | None:
        with self._lock:
            waiting = sorted(
                (
                    (historic_id, record)
                    for historic_id, record in self._records.items()
                    if record.state.published is not None
                    and (record.indexed_seq != record.seq or record.indexed_identity != identity)
                    and (record.retry_at is None or record.retry_at <= now)
                ),
                key=lambda pair: pair[1].seq,
            )
            if not waiting:
                return None
            historic_id, record = waiting[0]
            published = record.state.published
            if published is None:  # pragma: no cover - filtered above
                return None
            if record.stage_seq != record.seq or record.stage_identity != identity:
                record.stage_seq, record.stage_identity = record.seq, identity
                record.stage_part, record.stage_offset = ContentPart.PASSAGES, 0
                record.chunks_built, record.staged = False, {}
            return PendingHistoric(
                historic_id,
                record.seq,
                published.number,
                published.fingerprint,
                record.stage_part,
                record.stage_offset,
                record.chunks_built,
                record.failures,
            )

    def save_page(
        self,
        pending: PendingHistoric,
        part: ContentPart,
        entries: tuple[object, ...],
        next_part: ContentPart | None,
        next_offset: int,
    ) -> None:
        with self._lock:
            record = self._records.get(pending.historic_id)
            if record is None or record.stage_seq != pending.seq:
                return
            record.staged.setdefault(part, []).extend(entries)
            record.stage_part, record.stage_offset = next_part, next_offset
            record.failures = 0

    def staged(self, historic_id: str, seq: int) -> dict[ContentPart, tuple[object, ...]]:
        with self._lock:
            record = self._records.get(historic_id)
            if record is None or record.stage_seq != seq:
                return {}
            return {part: tuple(entries) for part, entries in record.staged.items()}

    def stage_chunks(
        self, historic_id: str, seq: int, identity: str, chunks: tuple[HistoricChunk, ...]
    ) -> None:
        with self._lock:
            record = self._records.get(historic_id)
            if record is None or record.stage_seq != seq:
                return
            known = {
                row.chunk.text_hash: row.vector
                for row in self._rows.values()
                if row.identity == identity and row.vector is not None
            }
            for key in [key for key in self._rows if key[:3] == (historic_id, seq, identity)]:
                del self._rows[key]
            for chunk in chunks:
                self._rows[(historic_id, seq, identity, chunk.chunk_id)] = _Row(
                    chunk, seq, identity, known.get(chunk.text_hash)
                )
            record.chunks_built, record.staged = True, {}

    def unembedded(
        self, historic_id: str, seq: int, identity: str, limit: int
    ) -> tuple[HistoricChunk, ...]:
        with self._lock:
            missing = [
                row.chunk
                for key, row in self._rows.items()
                if key[:3] == (historic_id, seq, identity) and row.vector is None
            ]
            return tuple(missing[: max(0, limit)])

    def save_vectors(
        self, historic_id: str, seq: int, identity: str, vectors: dict[str, Embedding]
    ) -> None:
        with self._lock:
            for chunk_id, vector in vectors.items():
                row = self._rows.get((historic_id, seq, identity, chunk_id))
                if row is not None:
                    row.vector = vector
            record = self._records.get(historic_id)
            if record is not None:
                record.failures = 0

    def embedding_budget(self, historic_id: str, now: datetime, hourly: int) -> int:
        with self._lock:
            record = self._records.get(historic_id)
            if record is None or record.embed_window != _hour(now):
                return hourly
            return max(0, hourly - record.embedded)

    def spend_embedding_budget(self, historic_id: str, now: datetime, count: int) -> None:
        with self._lock:
            record = self._records.get(historic_id)
            if record is None:
                return
            if record.embed_window != _hour(now):
                record.embed_window, record.embedded = _hour(now), 0
            record.embedded += count

    def complete(self, historic_id: str, seq: int, identity: str) -> bool:
        with self._lock:
            record = self._records.get(historic_id)
            if record is None or record.seq != seq or record.state.published is None:
                return False
            if self.unembedded(historic_id, seq, identity, 1):
                return False
            for key in [
                key for key in self._rows if key[0] == historic_id and key[1:3] != (seq, identity)
            ]:
                del self._rows[key]
            self._version += 1
            record.indexed_seq, record.indexed_identity = seq, identity
            record.failures, record.retry_at = 0, None
            return True

    def restart(self, historic_id: str, seq: int) -> None:
        with self._lock:
            record = self._records.get(historic_id)
            if record is not None and record.stage_seq == seq:
                record.stage_seq, record.stage_identity = None, None

    def record_failure(self, historic_id: str, retry_at: datetime) -> None:
        with self._lock:
            record = self._records.get(historic_id)
            if record is not None:
                record.failures += 1
                record.retry_at = retry_at

    def defer(self, historic_id: str, until: datetime) -> None:
        with self._lock:
            record = self._records.get(historic_id)
            if record is not None:
                record.retry_at = until

    def remove(self, historic_id: str) -> None:
        with self._lock:
            for key in [key for key in self._rows if key[0] == historic_id]:
                del self._rows[key]
            record = self._records.get(historic_id)
            if record is not None:
                record.indexed_seq = record.indexed_identity = None
                record.stage_seq = record.stage_identity = None
                record.staged = {}

    def _searchable(self, identity: str) -> list[tuple[_Row, _Record]]:
        found: list[tuple[_Row, _Record]] = []
        for (historic_id, seq, row_identity, _), row in self._rows.items():
            record = self._records.get(historic_id)
            if (
                record is not None
                and record.state.published is not None
                and row_identity == identity
                and record.indexed_identity == identity
                and record.indexed_seq == seq
                and row.vector is not None
            ):
                found.append((row, record))
        return found

    def search(
        self, query_text: str, query_embedding: Embedding, identity: str, limit: int
    ) -> tuple[HistoricMatch, ...]:
        with self._lock:
            candidates = self._searchable(identity)
            terms = set(_WORDS.findall(query_text.casefold()))
            overlap = {
                row.chunk.chunk_id: len(
                    terms.intersection(_WORDS.findall(row.chunk.text.casefold()))
                )
                for row, _ in candidates
            }
            lexical = sorted(
                (row.chunk.chunk_id for row, _ in candidates if overlap[row.chunk.chunk_id] > 0),
                key=lambda chunk_id: overlap[chunk_id],
                reverse=True,
            )[: limit * 2]
            semantic = [
                row.chunk.chunk_id
                for row, _ in sorted(
                    candidates,
                    key=lambda pair: _cosine(query_embedding, cast(Embedding, pair[0].vector)),
                    reverse=True,
                )[: limit * 2]
            ]
            fused = fuse(lexical, semantic)
            by_id = {row.chunk.chunk_id: (row, record) for row, record in candidates}
            matches = []
            for chunk_id, (lex, sem, score) in fused.items():
                row, record = by_id[chunk_id]
                published = record.state.published
                if published is None:  # pragma: no cover - filtered in _searchable
                    continue
                matches.append(
                    HistoricMatch(row.chunk, published.title, published.number, lex, sem, score)
                )
            return tuple(sorted(matches, key=lambda match: match.fused_score, reverse=True)[:limit])

    def version(self) -> int:
        with self._lock:
            return self._version

    def has_content(self, identity: str) -> bool:
        with self._lock:
            return bool(self._searchable(identity))


_CONSUMER = "historic_requirements"
# Long subjects rarely share every word with a passage, so lexical search asks for any of
# them, ranked by how many and how close (ADR-0102, amendment 1).
_QUERY_TERMS = 64


def any_of(query_text: str) -> str:
    """A `to_tsquery` text matching any of the query's distinct words."""
    terms = list(dict.fromkeys(_WORDS.findall(query_text.casefold())))[:_QUERY_TERMS]
    return " | ".join("'" + term.replace("'", "''") + "'" for term in terms)


def _int(value: object) -> int:
    return int(cast(int, value))


def _vector(value: Embedding) -> str:
    if len(value) != 768:
        raise ValueError(f"Knowledge embeddings must contain 768 values; received {len(value)}.")
    return "[" + ",".join(str(float(item)) for item in value) + "]"


def _embedding(value: object) -> Embedding:
    text = str(value).strip("[]")
    return tuple(float(item) for item in text.split(",")) if text else ()


def _chunk(row: tuple[object, ...]) -> HistoricChunk:
    historic_id, chunk_id, kind, field_name, text, text_hash, evidence = row
    return HistoricChunk(
        str(chunk_id),
        str(historic_id),
        HistoricSourceKind(str(kind)),
        str(field_name),
        str(text),
        str(text_hash),
        cast(dict[str, object], evidence),
    )


_CHUNK_COLUMNS = "historic_requirement_id, chunk_id, source_kind, field, text, text_hash, evidence"


class PostgresHistoricCorpus:
    """Both the historic copy and its corpus index; session-aware, so a withdrawal and
    its removal from search commit together."""

    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    # --- The copy ------------------------------------------------------------------------

    def cursor(self) -> int:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT seq FROM knowledge_event_cursors WHERE consumer = %s", (_CONSUMER,)
            ).fetchone()
        return int(cast(int, row[0])) if row else 0

    def advance(self, seq: int) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "INSERT INTO knowledge_event_cursors (consumer, seq) VALUES (%s, %s) "
                "ON CONFLICT (consumer) DO UPDATE "
                "SET seq = GREATEST(knowledge_event_cursors.seq, excluded.seq)",
                (_CONSUMER, seq),
            )

    def apply(self, seq: int, state: HistoricRequirementState) -> bool:
        published = state.published
        with self._store.connection() as connection:
            result = connection.execute(
                "INSERT INTO historic_requirement_state "
                "(historic_requirement_id, seq, payload, published, publication, title) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (historic_requirement_id) DO UPDATE SET seq = excluded.seq, "
                "payload = excluded.payload, published = excluded.published, "
                "publication = excluded.publication, title = excluded.title, "
                "failures = 0, retry_at = NULL "
                "WHERE excluded.seq > historic_requirement_state.seq",
                (
                    state.historic_requirement_id,
                    seq,
                    Jsonb(historic_requirement_state_to_payload(state)),
                    published is not None,
                    None if published is None else published.number,
                    "" if published is None else published.title,
                ),
            )
        return result.rowcount == 1

    def get(self, historic_id: str) -> HistoricRequirementState | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM historic_requirement_state WHERE historic_requirement_id = %s",
                (historic_id,),
            ).fetchone()
        return historic_requirement_state_from_payload(row[0]) if row else None

    def standing(self, historic_ids: tuple[str, ...]) -> dict[str, HistoricStanding]:
        if not historic_ids:
            return {}
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT historic_requirement_id, published, publication, title "
                "FROM historic_requirement_state WHERE historic_requirement_id = ANY(%s)",
                (list(historic_ids),),
            ).fetchall()
        return {
            str(row[0]): HistoricStanding(
                bool(row[1]), None if row[2] is None else _int(row[2]), str(row[3])
            )
            for row in rows
        }

    # --- The index -----------------------------------------------------------------------

    def next_pending(self, identity: str, now: datetime) -> PendingHistoric | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT historic_requirement_id, seq, publication, payload, stage_seq, "
                "stage_identity, stage_part, stage_offset, chunks_built, failures "
                "FROM historic_requirement_state WHERE published "
                "AND (indexed_seq IS DISTINCT FROM seq OR indexed_identity IS DISTINCT FROM %s) "
                "AND (retry_at IS NULL OR retry_at <= %s) "
                "ORDER BY seq LIMIT 1 FOR UPDATE SKIP LOCKED",
                (identity, now),
            ).fetchone()
            if row is None:
                return None
            historic_id, seq = str(row[0]), _int(row[1])
            state = historic_requirement_state_from_payload(row[3])
            if state.published is None:  # pragma: no cover - `published` is filtered above
                return None
            part: ContentPart | None
            if row[4] != seq or row[5] != identity:
                connection.execute(
                    "UPDATE historic_requirement_state SET stage_seq = %s, stage_identity = %s, "
                    "stage_part = 'passages', stage_offset = 0, chunks_built = false "
                    "WHERE historic_requirement_id = %s",
                    (seq, identity, historic_id),
                )
                connection.execute(
                    "DELETE FROM historic_content_staging WHERE historic_requirement_id = %s",
                    (historic_id,),
                )
                part, offset, built = ContentPart.PASSAGES, 0, False
            else:
                part = None if row[6] is None else ContentPart(str(row[6]))
                offset, built = _int(row[7]), bool(row[8])
        return PendingHistoric(
            historic_id,
            seq,
            state.published.number,
            state.published.fingerprint,
            part,
            offset,
            built,
            _int(row[9]),
        )

    def save_page(
        self,
        pending: PendingHistoric,
        part: ContentPart,
        entries: tuple[object, ...],
        next_part: ContentPart | None,
        next_offset: int,
    ) -> None:
        with self._store.connection() as connection:
            moved = connection.execute(
                "UPDATE historic_requirement_state SET stage_part = %s, stage_offset = %s, "
                "failures = 0 WHERE historic_requirement_id = %s AND stage_seq = %s "
                "AND stage_part = %s AND stage_offset = %s",
                (
                    None if next_part is None else next_part.value,
                    next_offset,
                    pending.historic_id,
                    pending.seq,
                    part.value,
                    pending.offset,
                ),
            )
            if moved.rowcount != 1:
                return  # Another worker read this page first, or a newer event arrived.
            with connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO historic_content_staging "
                    "(historic_requirement_id, seq, part, ordinal, entry) "
                    "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    [
                        (pending.historic_id, pending.seq, part.value, pending.offset + n, Jsonb(e))
                        for n, e in enumerate(entries)
                    ],
                )

    def staged(self, historic_id: str, seq: int) -> dict[ContentPart, tuple[object, ...]]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT part, entry FROM historic_content_staging "
                "WHERE historic_requirement_id = %s AND seq = %s ORDER BY part, ordinal",
                (historic_id, seq),
            ).fetchall()
        found: dict[ContentPart, list[object]] = {}
        for part, entry in rows:
            found.setdefault(ContentPart(str(part)), []).append(entry)
        return {part: tuple(entries) for part, entries in found.items()}

    def stage_chunks(
        self, historic_id: str, seq: int, identity: str, chunks: tuple[HistoricChunk, ...]
    ) -> None:
        with self._store.connection() as connection:
            built = connection.execute(
                "UPDATE historic_requirement_state SET chunks_built = true "
                "WHERE historic_requirement_id = %s AND stage_seq = %s AND NOT chunks_built",
                (historic_id, seq),
            )
            if built.rowcount != 1:
                return
            connection.execute(
                "DELETE FROM historic_knowledge_chunks WHERE historic_requirement_id = %s "
                "AND seq = %s AND embedding_identity = %s",
                (historic_id, seq, identity),
            )
            with connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO historic_knowledge_chunks (historic_requirement_id, seq, "
                    "embedding_identity, chunk_id, source_kind, field, text, text_hash, "
                    "evidence) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT DO NOTHING",
                    [
                        (
                            historic_id,
                            seq,
                            identity,
                            c.chunk_id,
                            c.source_kind.value,
                            c.field,
                            c.text,
                            c.text_hash,
                            Jsonb(c.evidence),
                        )
                        for c in chunks
                    ],
                )
            # Unchanged text keeps the vector it already has.
            connection.execute(
                "UPDATE historic_knowledge_chunks AS fresh SET embedding = known.embedding "
                "FROM (SELECT DISTINCT ON (text_hash) text_hash, embedding "
                "      FROM historic_knowledge_chunks "
                "      WHERE embedding_identity = %s AND embedding IS NOT NULL) AS known "
                "WHERE fresh.historic_requirement_id = %s AND fresh.seq = %s "
                "AND fresh.embedding_identity = %s AND fresh.embedding IS NULL "
                "AND fresh.text_hash = known.text_hash",
                (identity, historic_id, seq, identity),
            )
            connection.execute(
                "DELETE FROM historic_content_staging WHERE historic_requirement_id = %s",
                (historic_id,),
            )

    def unembedded(
        self, historic_id: str, seq: int, identity: str, limit: int
    ) -> tuple[HistoricChunk, ...]:
        if limit <= 0:
            return ()
        with self._store.connection() as connection:
            rows = connection.execute(
                f"SELECT {_CHUNK_COLUMNS} FROM historic_knowledge_chunks "
                "WHERE historic_requirement_id = %s AND seq = %s AND embedding_identity = %s "
                "AND embedding IS NULL ORDER BY chunk_id LIMIT %s",
                (historic_id, seq, identity, limit),
            ).fetchall()
        return tuple(_chunk(tuple(row)) for row in rows)

    def save_vectors(
        self, historic_id: str, seq: int, identity: str, vectors: dict[str, Embedding]
    ) -> None:
        with self._store.connection() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    "UPDATE historic_knowledge_chunks SET embedding = %s::vector "
                    "WHERE historic_requirement_id = %s AND seq = %s "
                    "AND embedding_identity = %s AND chunk_id = %s",
                    [
                        (_vector(vector), historic_id, seq, identity, chunk_id)
                        for chunk_id, vector in vectors.items()
                    ],
                )
            connection.execute(
                "UPDATE historic_requirement_state SET failures = 0 "
                "WHERE historic_requirement_id = %s",
                (historic_id,),
            )

    def embedding_budget(self, historic_id: str, now: datetime, hourly: int) -> int:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT embed_window, embedded FROM historic_requirement_state "
                "WHERE historic_requirement_id = %s",
                (historic_id,),
            ).fetchone()
        if row is None or row[0] != _hour(now):
            return hourly
        return max(0, hourly - _int(row[1]))

    def spend_embedding_budget(self, historic_id: str, now: datetime, count: int) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "UPDATE historic_requirement_state SET "
                "embedded = CASE WHEN embed_window = %s THEN embedded + %s ELSE %s END, "
                "embed_window = %s WHERE historic_requirement_id = %s",
                (_hour(now), count, count, _hour(now), historic_id),
            )

    def complete(self, historic_id: str, seq: int, identity: str) -> bool:
        with self._store.connection() as connection:
            moved = connection.execute(
                "UPDATE historic_requirement_state SET indexed_seq = %s, indexed_identity = %s, "
                "failures = 0, retry_at = NULL "
                "WHERE historic_requirement_id = %s AND seq = %s AND published "
                "AND NOT EXISTS (SELECT 1 FROM historic_knowledge_chunks "
                "  WHERE historic_requirement_id = %s AND seq = %s "
                "  AND embedding_identity = %s AND embedding IS NULL)",
                (seq, identity, historic_id, seq, historic_id, seq, identity),
            )
            if moved.rowcount != 1:
                return False
            connection.execute(
                "DELETE FROM historic_knowledge_chunks WHERE historic_requirement_id = %s "
                "AND (seq <> %s OR embedding_identity <> %s)",
                (historic_id, seq, identity),
            )
            connection.execute("SELECT nextval('historic_corpus_version_seq')")
        return True

    def restart(self, historic_id: str, seq: int) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "UPDATE historic_requirement_state SET stage_seq = NULL, stage_identity = NULL "
                "WHERE historic_requirement_id = %s AND stage_seq = %s",
                (historic_id, seq),
            )

    def record_failure(self, historic_id: str, retry_at: datetime) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "UPDATE historic_requirement_state SET failures = failures + 1, retry_at = %s "
                "WHERE historic_requirement_id = %s",
                (retry_at, historic_id),
            )

    def defer(self, historic_id: str, until: datetime) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "UPDATE historic_requirement_state SET retry_at = %s "
                "WHERE historic_requirement_id = %s",
                (until, historic_id),
            )

    def remove(self, historic_id: str) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "DELETE FROM historic_knowledge_chunks WHERE historic_requirement_id = %s",
                (historic_id,),
            )
            connection.execute(
                "DELETE FROM historic_content_staging WHERE historic_requirement_id = %s",
                (historic_id,),
            )
            connection.execute(
                "UPDATE historic_requirement_state SET indexed_seq = NULL, "
                "indexed_identity = NULL, stage_seq = NULL, stage_identity = NULL "
                "WHERE historic_requirement_id = %s",
                (historic_id,),
            )

    _SEARCHABLE = (
        "FROM historic_knowledge_chunks c JOIN historic_requirement_state s "
        "USING (historic_requirement_id) WHERE s.published AND c.seq = s.indexed_seq "
        "AND c.embedding_identity = s.indexed_identity AND c.embedding_identity = %s "
        "AND c.embedding IS NOT NULL"
    )

    def search(
        self, query_text: str, query_embedding: Embedding, identity: str, limit: int
    ) -> tuple[HistoricMatch, ...]:
        columns = (
            "c.historic_requirement_id, c.chunk_id, c.source_kind, c.field, c.text, "
            "c.text_hash, c.evidence, s.title, s.publication"
        )
        terms = any_of(query_text)
        with self._store.connection() as connection:
            lexical = (
                connection.execute(
                    f"SELECT {columns}, ts_rank_cd(c.search_document, to_tsquery('simple', %s)) "
                    f"score {self._SEARCHABLE} "
                    "AND c.search_document @@ to_tsquery('simple', %s) "
                    "ORDER BY score DESC, c.chunk_id LIMIT %s",
                    (terms, identity, terms, limit * 2),
                ).fetchall()
                if terms
                else []
            )
            semantic = connection.execute(
                f"SELECT {columns}, c.embedding <=> %s::vector distance {self._SEARCHABLE} "
                "ORDER BY distance, c.chunk_id LIMIT %s",
                (_vector(query_embedding), identity, limit * 2),
            ).fetchall()
        rows = {str(row[1]): row for row in (*lexical, *semantic)}
        fused = fuse([str(row[1]) for row in lexical], [str(row[1]) for row in semantic])
        matches = [
            HistoricMatch(
                _chunk(tuple(rows[chunk_id][:7])),
                str(rows[chunk_id][7]),
                _int(rows[chunk_id][8]),
                lex,
                sem,
                score,
            )
            for chunk_id, (lex, sem, score) in fused.items()
        ]
        return tuple(sorted(matches, key=lambda match: match.fused_score, reverse=True)[:limit])

    def version(self) -> int:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT CASE WHEN is_called THEN last_value ELSE 0 END "
                "FROM historic_corpus_version_seq"
            ).fetchone()
        return int(cast(int, row[0])) if row else 0

    def has_content(self, identity: str) -> bool:
        with self._store.connection() as connection:
            row = connection.execute(
                f"SELECT EXISTS (SELECT 1 {self._SEARCHABLE})", (identity,)
            ).fetchone()
        return bool(row and row[0])
