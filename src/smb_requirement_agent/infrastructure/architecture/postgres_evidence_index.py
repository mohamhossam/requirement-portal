"""PostgreSQL lexical and exact-vector retrieval for released evidence."""

from __future__ import annotations

import hashlib

import psycopg

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.application.ports.architecture_rag import (
    EmbeddingPort,
    EvidenceChunk,
)
from smb_requirement_agent.application.ports.architecture_tokenizer import ArchitectureTokenizerPort
from smb_requirement_agent.infrastructure.persistence.postgres_connector import PostgresConnector


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PostgresEvidenceIndex:
    def __init__(
        self,
        connector: PostgresConnector,
        embeddings: EmbeddingPort,
        tokenizer: ArchitectureTokenizerPort,
    ) -> None:
        self._connector = connector
        self._embeddings = embeddings
        self._tokenizer = tokenizer

    @property
    def embedding_model(self) -> str:
        return self._embeddings.model

    @property
    def profile(self) -> str:
        return f"{self._embeddings.model}:{self._tokenizer.profile}:section-v2"

    @staticmethod
    def _vector(values: tuple[float, ...]) -> str:
        return "[" + ",".join(str(value) for value in values) + "]"

    def store(self, release_id: str, index_id: str, chunks: tuple[EvidenceChunk, ...]) -> None:
        """Store an index, embedding only passage texts this model has not embedded before."""
        model = self._embeddings.model
        hashes = tuple(_hash(chunk.text) for chunk in chunks)
        try:
            with self._connector.connection() as connection:
                rows = connection.execute(
                    "SELECT content_hash, embedding::text FROM architecture_embedding_cache "
                    "WHERE model = %s AND content_hash = ANY(%s)",
                    (model, list(set(hashes))),
                ).fetchall()
        except psycopg.Error as exc:
            raise PersistenceError("Architecture embedding cache read failed.") from exc
        cached = {str(row[0]): str(row[1]) for row in rows}
        missing = {key: chunk.text for key, chunk in zip(hashes, chunks, strict=True)}
        missing = {key: text for key, text in missing.items() if key not in cached}
        embedded = dict(
            zip(
                missing,
                (
                    self._vector(vector)
                    for vector in self._embeddings.embed(tuple(missing.values()))
                ),
                strict=True,
            )
        )
        try:
            with self._connector.connection() as connection:
                for key, vector in embedded.items():
                    connection.execute(
                        "INSERT INTO architecture_embedding_cache (model, content_hash, embedding) "
                        "VALUES (%s, %s, %s::vector) ON CONFLICT DO NOTHING",
                        (model, key, vector),
                    )
                connection.execute(
                    "INSERT INTO architecture_knowledge_indexes (index_id, release_id) "
                    "VALUES (%s, %s)",
                    (index_id, release_id),
                )
                for chunk, key in zip(chunks, hashes, strict=True):
                    connection.execute(
                        "INSERT INTO architecture_knowledge_chunks "
                        "(index_id, chunk_id, document_version_id, source_label, location, "
                        "content, embedding) VALUES (%s, %s, %s, %s, %s, %s, %s::vector)",
                        (
                            index_id,
                            chunk.id,
                            chunk.document_version_id,
                            chunk.source_label,
                            chunk.location,
                            chunk.text,
                            embedded.get(key) or cached[key],
                        ),
                    )
        except psycopg.Error as exc:
            raise PersistenceError("Architecture evidence indexing failed.") from exc

    def retrieve(self, index_id: str, query: str, limit: int) -> tuple[EvidenceChunk, ...]:
        vector = self._vector(self._embeddings.embed((query,))[0])
        try:
            with self._connector.connection() as connection:
                rows = connection.execute(
                    """
                    WITH lexical AS (
                      SELECT chunk_id, row_number() OVER (
                        ORDER BY ts_rank_cd(search_text, plainto_tsquery('simple', %s)) DESC
                      ) AS rank
                      FROM architecture_knowledge_chunks
                      WHERE index_id = %s
                        AND search_text @@ plainto_tsquery('simple', %s)
                      ORDER BY ts_rank_cd(search_text, plainto_tsquery('simple', %s)) DESC
                      LIMIT 20
                    ), semantic AS (
                      SELECT chunk_id, row_number() OVER (ORDER BY embedding <=> %s::vector) AS rank
                      FROM architecture_knowledge_chunks WHERE index_id = %s
                      ORDER BY embedding <=> %s::vector LIMIT 20
                    ), ranked AS (
                      SELECT chunk_id, sum(score) AS score FROM (
                        SELECT chunk_id, 1.0 / (60 + rank) AS score FROM lexical
                        UNION ALL
                        SELECT chunk_id, 1.0 / (60 + rank) AS score FROM semantic
                      ) results GROUP BY chunk_id
                    )
                    SELECT c.chunk_id, c.source_label, c.location, c.content,
                           c.document_version_id
                    FROM ranked r JOIN architecture_knowledge_chunks c
                      ON c.index_id = %s AND c.chunk_id = r.chunk_id
                    ORDER BY r.score DESC LIMIT %s
                    """,
                    (
                        query,
                        index_id,
                        query,
                        query,
                        vector,
                        index_id,
                        vector,
                        index_id,
                        limit,
                    ),
                ).fetchall()
            return tuple(
                EvidenceChunk(
                    str(row[0]),
                    str(row[1]),
                    str(row[2]),
                    str(row[3]),
                    str(row[4]) if row[4] is not None else None,
                )
                for row in rows
            )
        except psycopg.Error as exc:
            raise PersistenceError("Architecture evidence retrieval failed.") from exc

    def get(self, index_id: str, chunk_id: str) -> EvidenceChunk | None:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    "SELECT chunk_id, source_label, location, content, document_version_id "
                    "FROM architecture_knowledge_chunks WHERE index_id = %s AND chunk_id = %s",
                    (index_id, chunk_id),
                ).fetchone()
            if row is None:
                return None
            return EvidenceChunk(
                str(row[0]),
                str(row[1]),
                str(row[2]),
                str(row[3]),
                str(row[4]) if row[4] is not None else None,
            )
        except psycopg.Error as exc:
            raise PersistenceError("Architecture evidence read failed.") from exc

    def system_chunk(self, index_id: str, system_id: str) -> EvidenceChunk | None:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    "SELECT chunk_id, source_label, location, content, document_version_id "
                    "FROM architecture_knowledge_chunks WHERE index_id = %s "
                    "AND document_version_id IS NULL "
                    "AND (location = %s OR starts_with(location, %s)) "
                    "ORDER BY length(location), location LIMIT 1",
                    (index_id, f"system {system_id}", f"system {system_id},"),
                ).fetchone()
            if row is None:
                return None
            return EvidenceChunk(str(row[0]), str(row[1]), str(row[2]), str(row[3]), None)
        except psycopg.Error as exc:
            raise PersistenceError("Architecture evidence read failed.") from exc
