"""Offline hybrid retrieval over immutable release chunks."""

from __future__ import annotations

from smb_requirement_agent.application.ports.architecture_rag import (
    ArchitectureEvidenceIndexPort,
    EmbeddingPort,
    EvidenceChunk,
)
from smb_requirement_agent.application.ports.architecture_tokenizer import ArchitectureTokenizerPort


class InMemoryEvidenceIndex(ArchitectureEvidenceIndexPort):
    def __init__(self, embeddings: EmbeddingPort, tokenizer: ArchitectureTokenizerPort) -> None:
        self._embeddings = embeddings
        self._tokenizer = tokenizer
        self._entries: dict[str, tuple[tuple[EvidenceChunk, tuple[float, ...]], ...]] = {}
        # Vectors by (model, passage text): a rebuild only embeds what changed.
        self._cache: dict[tuple[str, str], tuple[float, ...]] = {}

    @property
    def embedding_model(self) -> str:
        return self._embeddings.model

    @property
    def profile(self) -> str:
        return f"{self._embeddings.model}:{self._tokenizer.profile}:section-v2"

    def store(self, release_id: str, index_id: str, chunks: tuple[EvidenceChunk, ...]) -> None:
        if index_id in self._entries:
            raise ValueError("Evidence indexes are immutable.")
        model = self._embeddings.model
        missing = tuple(
            dict.fromkeys(chunk.text for chunk in chunks if (model, chunk.text) not in self._cache)
        )
        self._cache.update(
            ((model, text), vector)
            for text, vector in zip(missing, self._embeddings.embed(missing), strict=True)
        )
        self._entries[index_id] = tuple(
            (chunk, self._cache[(model, chunk.text)]) for chunk in chunks
        )

    def retrieve(self, release_id: str, query: str, limit: int) -> tuple[EvidenceChunk, ...]:
        entries = self._entries.get(release_id, ())
        if not entries:
            return ()
        query_vector = self._embeddings.embed((query,))[0]
        terms = set(query.casefold().split())
        lexical = sorted(entries, key=lambda row: -len(terms & set(row[0].text.casefold().split())))
        vector = sorted(
            entries, key=lambda row: -sum(a * b for a, b in zip(query_vector, row[1], strict=True))
        )
        ranks: dict[str, float] = {}
        for ordering in (lexical[:20], vector[:20]):
            for rank, (chunk, _) in enumerate(ordering, 1):
                ranks[chunk.id] = ranks.get(chunk.id, 0.0) + 1.0 / (60 + rank)
        by_id = {chunk.id: chunk for chunk, _ in entries}
        return tuple(
            by_id[chunk_id]
            for chunk_id in sorted(ranks, key=lambda key: ranks[key], reverse=True)[:limit]
        )

    def get(self, release_id: str, chunk_id: str) -> EvidenceChunk | None:
        return next(
            (chunk for chunk, _ in self._entries.get(release_id, ()) if chunk.id == chunk_id), None
        )

    def system_chunk(self, index_id: str, system_id: str) -> EvidenceChunk | None:
        own = f"system {system_id}"
        return next(
            (
                chunk
                for chunk, _ in self._entries.get(index_id, ())
                if chunk.document_version_id is None
                and (chunk.location == own or chunk.location.startswith(f"{own},"))
            ),
            None,
        )
