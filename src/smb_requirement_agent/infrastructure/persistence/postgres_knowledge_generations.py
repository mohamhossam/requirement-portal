"""Durable isolated search generations with optimistic source checks and atomic activation."""

from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Jsonb

from smb_requirement_agent.application.errors import KnowledgeGenerationError, ModelTransportError
from smb_requirement_agent.application.ports.knowledge_index_generations import IndexGeneration
from smb_requirement_agent.application.ports.requirement_knowledge import (
    Embedding,
    RequirementKnowledgeIndexPort,
)
from smb_requirement_agent.domain.knowledge.entities import KnowledgeChunk, KnowledgeMatch
from smb_requirement_agent.infrastructure.persistence.postgres_requirement_knowledge import (
    _chunk_from_payload,
    _chunk_payload,
    _object,
    _vector,
)
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import DbConnection, _integer
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class PostgresKnowledgeIndexGenerations:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def begin_rebuild(self, identity: str) -> IndexGeneration:
        with self._store.connection() as connection:
            row = connection.execute(
                "INSERT INTO knowledge_index_generations "
                "(generation_id,embedding_identity,status) VALUES (%s,%s,'staging') "
                "ON CONFLICT (embedding_identity) WHERE status='staging' "
                "DO UPDATE SET embedding_identity=EXCLUDED.embedding_identity "
                "RETURNING generation_id,embedding_identity,status",
                (str(uuid4()), identity),
            ).fetchone()
        if row is None:
            raise ModelTransportError("index_required")
        return IndexGeneration(str(row[0]), str(row[1]), str(row[2]))

    def list_generations(self) -> tuple[IndexGeneration, ...]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT generation_id,embedding_identity,status FROM knowledge_index_generations "
                "ORDER BY created_at,generation_id"
            ).fetchall()
        return tuple(IndexGeneration(str(row[0]), str(row[1]), str(row[2])) for row in rows)

    def staging_index(self, generation_id: str) -> RequirementKnowledgeIndexPort:
        return _PostgresGenerationIndex(self._store, generation_id=generation_id)

    def active_index(self, identity: str) -> RequirementKnowledgeIndexPort:
        return _PostgresGenerationIndex(self._store, identity=identity)

    def activate(self, generation_id: str) -> None:
        with self._store.transaction():
            with self._store.connection() as connection:
                # Block new sources and source changes only during the short validation/switch.
                connection.execute("LOCK TABLE requirements IN SHARE MODE")
                connection.execute("LOCK TABLE knowledge_source_changes IN SHARE MODE")
                connection.execute("LOCK TABLE knowledge_index_generations IN EXCLUSIVE MODE")
                row = connection.execute(
                    "SELECT generation_id FROM knowledge_index_generations WHERE generation_id=%s",
                    (generation_id,),
                ).fetchone()
                if row is None or _pending(connection, generation_id, 1):
                    raise ModelTransportError("index_required")
                connection.execute(
                    "UPDATE knowledge_index_generations SET status='retired' WHERE status='active'"
                )
                connection.execute(
                    "UPDATE knowledge_index_generations SET status='active' WHERE generation_id=%s",
                    (generation_id,),
                )


def _pending(
    connection: DbConnection, generation_id: str, limit: int, after: str = ""
) -> tuple[tuple[RequirementId, int], ...]:
    rows = connection.execute(
        "SELECT s.requirement_id,s.change_number FROM knowledge_source_changes s "
        "LEFT JOIN knowledge_generation_index i "
        "ON i.requirement_id=s.requirement_id AND i.generation_id=%s "
        "WHERE s.requirement_id > %s AND i.source_change IS DISTINCT FROM s.change_number "
        "ORDER BY s.requirement_id LIMIT %s",
        (generation_id, after, limit),
    ).fetchall()
    return tuple((RequirementId(str(row[0])), _integer(row[1])) for row in rows)


class _PostgresGenerationIndex:
    def __init__(
        self,
        store: PostgresSession,
        *,
        generation_id: str | None = None,
        identity: str | None = None,
    ) -> None:
        self._store = store
        self._generation_id = generation_id
        self._identity = identity

    def _key(self, connection: DbConnection) -> str:
        if self._generation_id:
            row = connection.execute(
                "SELECT generation_id FROM knowledge_index_generations WHERE generation_id=%s",
                (self._generation_id,),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT generation_id FROM knowledge_index_generations "
                "WHERE status='active' AND embedding_identity=%s",
                (self._identity,),
            ).fetchone()
        if row is None:
            raise ModelTransportError("index_required")
        return str(row[0])

    def pending_sources(self, limit: int, after: str = "") -> tuple[tuple[RequirementId, int], ...]:
        with self._store.connection() as connection:
            return _pending(connection, self._key(connection), limit, after)

    def indexed_fingerprint(self, requirement_id: RequirementId) -> str | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT corpus_fingerprint FROM knowledge_generation_index "
                "WHERE generation_id=%s AND requirement_id=%s",
                (self._key(connection), requirement_id.value),
            ).fetchone()
        return str(row[0]) if row else None

    def replace_if_current(
        self,
        requirement_id: RequirementId,
        expected_change: int,
        corpus_fingerprint: str,
        chunks: tuple[KnowledgeChunk, ...],
        embeddings: tuple[Embedding, ...],
    ) -> bool:
        if len(chunks) != len(embeddings):
            raise KnowledgeGenerationError("Each knowledge chunk requires one embedding.")
        with self._store.transaction():
            with self._store.connection() as connection:
                generation_id = self._key(connection)
                row = connection.execute(
                    "SELECT change_number FROM knowledge_source_changes "
                    "WHERE requirement_id=%s AND change_number=%s FOR UPDATE",
                    (requirement_id.value, expected_change),
                ).fetchone()
                if row is None:
                    return False
                connection.execute(
                    "DELETE FROM knowledge_generation_chunks "
                    "WHERE generation_id=%s AND requirement_id=%s",
                    (generation_id, requirement_id.value),
                )
                for chunk, embedding in zip(chunks, embeddings, strict=True):
                    connection.execute(
                        "INSERT INTO knowledge_generation_chunks "
                        "(generation_id,chunk_id,requirement_id,payload,embedding) "
                        "VALUES (%s,%s,%s,%s,%s::vector)",
                        (
                            generation_id,
                            chunk.id.value,
                            requirement_id.value,
                            Jsonb(_chunk_payload(chunk)),
                            _vector(embedding),
                        ),
                    )
                connection.execute(
                    "INSERT INTO knowledge_generation_index "
                    "(generation_id,requirement_id,corpus_fingerprint,source_change) "
                    "VALUES (%s,%s,%s,%s) "
                    "ON CONFLICT (generation_id,requirement_id) DO UPDATE SET "
                    "corpus_fingerprint=EXCLUDED.corpus_fingerprint,"
                    "source_change=EXCLUDED.source_change",
                    (generation_id, requirement_id.value, corpus_fingerprint, expected_change),
                )
                return True

    def replace(
        self,
        requirement_id: RequirementId,
        corpus_fingerprint: str,
        chunks: tuple[KnowledgeChunk, ...],
        embeddings: tuple[Embedding, ...],
    ) -> None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT change_number FROM knowledge_source_changes WHERE requirement_id=%s",
                (requirement_id.value,),
            ).fetchone()
        if row is None or not self.replace_if_current(
            requirement_id, _integer(row[0]), corpus_fingerprint, chunks, embeddings
        ):
            raise ModelTransportError("index_required")

    def search(
        self,
        query_text: str,
        query_embedding: Embedding,
        exclude_requirement_id: RequirementId | None,
        limit: int,
    ) -> tuple[KnowledgeMatch, ...]:
        with self._store.connection() as connection:
            key = self._key(connection)
            lexical = connection.execute(
                "SELECT chunk_id,payload,"
                "ts_rank_cd(search_document,websearch_to_tsquery('simple',%s)) score "
                "FROM knowledge_generation_chunks WHERE generation_id=%s "
                "AND requirement_id IS DISTINCT FROM %s "
                "AND search_document @@ websearch_to_tsquery('simple',%s) "
                "ORDER BY score DESC,chunk_id LIMIT %s",
                (
                    query_text,
                    key,
                    (exclude_requirement_id.value if exclude_requirement_id else None),
                    query_text,
                    limit,
                ),
            ).fetchall()
            semantic = connection.execute(
                "SELECT chunk_id,payload,embedding <=> %s::vector distance "
                "FROM knowledge_generation_chunks WHERE generation_id=%s "
                "AND requirement_id IS DISTINCT FROM %s "
                "ORDER BY distance,chunk_id LIMIT %s",
                (
                    _vector(query_embedding),
                    key,
                    (exclude_requirement_id.value if exclude_requirement_id else None),
                    limit,
                ),
            ).fetchall()
        lexical_rank = {str(row[0]): rank for rank, row in enumerate(lexical, 1)}
        semantic_rank = {str(row[0]): rank for rank, row in enumerate(semantic, 1)}
        rows = {str(row[0]): row for row in (*lexical, *semantic)}
        matches = [
            KnowledgeMatch(
                _chunk_from_payload(_object(row[1])),
                lexical_rank.get(chunk_id),
                semantic_rank.get(chunk_id),
                (1 / (60 + lexical_rank[chunk_id]) if chunk_id in lexical_rank else 0)
                + (1 / (60 + semantic_rank[chunk_id]) if chunk_id in semantic_rank else 0),
            )
            for chunk_id, row in rows.items()
        ]
        return tuple(sorted(matches, key=lambda item: item.fused_score, reverse=True)[:limit])

    def get_chunks(self, chunk_ids: tuple[str, ...]) -> tuple[KnowledgeChunk, ...]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM knowledge_generation_chunks "
                "WHERE generation_id=%s AND chunk_id=ANY(%s)",
                (self._key(connection), list(chunk_ids)),
            ).fetchall()
        return tuple(_chunk_from_payload(_object(row[0])) for row in rows)
