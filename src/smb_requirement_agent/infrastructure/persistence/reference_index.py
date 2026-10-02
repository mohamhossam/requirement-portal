"""Hybrid reviewed-document indexes with embedding-identity isolation."""

from __future__ import annotations

import math
import re
from threading import RLock
from typing import cast

from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from smb_requirement_agent.application.ports.document_library import DocumentLibraryPort
from smb_requirement_agent.application.ports.reference_index import ReferenceChunk
from smb_requirement_agent.application.ports.requirement_knowledge import Embedding
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession


class Utf8BudgetCounter:
    """Conservative byte budget, not an English chars/4 estimate.

    One UTF-8 byte is charged as one budget unit, never a measured model token.
    A dated model-specific qualification measures representative chunks separately.
    Identity prevents silently mixing it with a later model-specific counter.
    """

    @property
    def identity(self) -> str:
        return "utf8-byte-upper-bound-v1"

    def count(self, text: str) -> int:
        return len(text.encode("utf-8"))


def query_terms(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"\w+", text.casefold())))[:24]


def fuse(lexical: list[str], semantic: list[str], limit: int) -> tuple[str, ...]:
    scores: dict[str, float] = {}
    for branch in (lexical, semantic):
        for rank, key in enumerate(branch, 1):
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
    return tuple(sorted(scores, key=lambda key: (-scores[key], key))[:limit])


class InMemoryReferenceIndex:
    def manifest(self, identity: str, publication_id: str) -> tuple[tuple[str, str], ...]:
        with self._lock:
            return tuple(
                sorted(
                    (c.id, c.content_hash)
                    for (generation, _), (c, _) in self._chunks.items()
                    if generation == identity and c.publication_id == publication_id
                )
            )

    def __init__(self, lock: RLock, documents: DocumentLibraryPort) -> None:
        self._lock = lock
        self._documents = documents
        self._chunks: dict[tuple[str, str], tuple[ReferenceChunk, Embedding]] = {}
        self._cache: dict[tuple[str, str], Embedding] = {}

    def snapshot_state(self) -> object:
        return dict(self._chunks), dict(self._cache)

    def restore_state(self, state: object) -> None:
        self._chunks, self._cache = cast(
            tuple[
                dict[tuple[str, str], tuple[ReferenceChunk, Embedding]],
                dict[tuple[str, str], Embedding],
            ],
            state,
        )

    def cached(self, identity: str, content_hash: str) -> Embedding | None:
        with self._lock:
            return self._cache.get((identity, content_hash))

    def stage(
        self, identity: str, chunks: tuple[ReferenceChunk, ...], vectors: tuple[Embedding, ...]
    ) -> None:
        with self._lock:
            for chunk, vector in zip(chunks, vectors, strict=True):
                self._chunks[identity, chunk.id] = (chunk, vector)
                self._cache[identity, chunk.content_hash] = vector

    def search(
        self, identity: str, text: str, vector: Embedding, limit: int
    ) -> tuple[ReferenceChunk, ...]:
        with self._lock:
            items = {
                c.id: (c, v)
                for (generation, _), (c, v) in self._chunks.items()
                if generation == identity
                and (source := self._documents.get(c.document_id)) is not None
                and source.published_id == c.publication_id
            }
        terms = set(query_terms(text))
        lexical_scores = {
            key: len(terms & set(re.findall(r"\w+", c.search_text.casefold())))
            for key, (c, _) in items.items()
        }
        lexical = sorted(
            (key for key in items if lexical_scores[key]),
            key=lambda key: (-lexical_scores[key], key),
        )[:100]
        norm = math.sqrt(sum(x * x for x in vector))
        semantic_scores = {
            key: sum(a * b for a, b in zip(vector, v, strict=True))
            / (norm * math.sqrt(sum(x * x for x in v)))
            for key, (_, v) in items.items()
        }
        semantic = sorted(items, key=lambda key: (-semantic_scores[key], key))[:100]
        return tuple(items[key][0] for key in fuse(lexical, semantic, limit))


class PostgresReferenceIndex:
    def manifest(self, identity: str, publication_id: str) -> tuple[tuple[str, str], ...]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT id,payload->>'content_hash' FROM library_chunks "
                "WHERE identity=%s AND publication_id=%s ORDER BY id",
                (identity, publication_id),
            ).fetchall()
        return tuple((str(r[0]), str(r[1])) for r in rows)

    def __init__(self, store: PostgresSession) -> None:
        self._store = store
        self._codec = TypeAdapter(ReferenceChunk)

    def cached(self, identity: str, content_hash: str) -> Embedding | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT embedding::text FROM library_embedding_cache "
                "WHERE identity=%s AND content_hash=%s",
                (identity, content_hash),
            ).fetchone()
        return tuple(float(v) for v in str(row[0]).strip("[]").split(",")) if row else None

    def stage(
        self, identity: str, chunks: tuple[ReferenceChunk, ...], vectors: tuple[Embedding, ...]
    ) -> None:
        with self._store.connection() as connection:
            for chunk, vector in zip(chunks, vectors, strict=True):
                encoded = "[" + ",".join(str(v) for v in vector) + "]"
                connection.execute(
                    """INSERT INTO library_embedding_cache(identity,content_hash,embedding)
                    VALUES (%s,%s,%s::vector) ON CONFLICT DO NOTHING""",
                    (identity, chunk.content_hash, encoded),
                )
                connection.execute(
                    """INSERT INTO library_chunks
                    (identity,id,document_id,publication_id,search_text,payload,embedding)
                    VALUES (%s,%s,%s,%s,%s,%s,%s::vector) ON CONFLICT DO NOTHING""",
                    (
                        identity,
                        chunk.id,
                        chunk.document_id,
                        chunk.publication_id,
                        chunk.search_text,
                        Jsonb(self._codec.dump_python(chunk, mode="json")),
                        encoded,
                    ),
                )

    def search(
        self, identity: str, text: str, vector: Embedding, limit: int
    ) -> tuple[ReferenceChunk, ...]:
        terms = query_terms(text)
        # Only word characters reach the tsquery grammar; OR is bounded to 24 unique terms.
        lexical_query = " | ".join("'" + term + "'" for term in terms)
        encoded = "[" + ",".join(str(v) for v in vector) + "]"
        eligible = """FROM library_chunks c JOIN library_documents d ON d.id=c.document_id
            AND d.published_id=c.publication_id WHERE c.identity=%s"""
        with self._store.connection() as connection:
            lexical = (
                connection.execute(
                    "SELECT c.id,c.payload "
                    + eligible
                    + " AND c.lexical @@ to_tsquery('simple',%s) "
                    "ORDER BY ts_rank_cd(c.lexical,to_tsquery('simple',%s)) DESC,c.id LIMIT 100",
                    (identity, lexical_query, lexical_query),
                ).fetchall()
                if terms
                else []
            )
            semantic = connection.execute(
                "SELECT c.id,c.payload "
                + eligible
                + " ORDER BY c.embedding <=> %s::vector,c.id LIMIT 100",
                (identity, encoded),
            ).fetchall()
        chunks = {str(row[0]): self._codec.validate_python(row[1]) for row in (*lexical, *semantic)}
        return tuple(
            chunks[key]
            for key in fuse([str(r[0]) for r in lexical], [str(r[0]) for r in semantic], limit)
        )
