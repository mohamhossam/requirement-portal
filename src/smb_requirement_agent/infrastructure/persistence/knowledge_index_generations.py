"""In-memory isolated vector generations; shares authoritative source-change locking."""

from __future__ import annotations

from threading import RLock
from typing import Any
from uuid import uuid4

from smb_requirement_agent.application.errors import ModelTransportError
from smb_requirement_agent.application.ports.knowledge_index_generations import IndexGeneration
from smb_requirement_agent.application.ports.requirement_knowledge import (
    Embedding,
    RequirementKnowledgeIndexPort,
)
from smb_requirement_agent.domain.knowledge.entities import KnowledgeChunk, KnowledgeMatch
from smb_requirement_agent.domain.shared.identifiers import RequirementId
from smb_requirement_agent.infrastructure.persistence.requirement_knowledge_repository import (
    InMemoryRequirementKnowledgeStore,
)


class InMemoryKnowledgeIndexGenerations:
    def __init__(self, sources: InMemoryRequirementKnowledgeStore, lock: RLock) -> None:
        self._sources = sources
        self._lock = lock
        self._generations: dict[str, IndexGeneration] = {}
        self._indexes: dict[str, InMemoryRequirementKnowledgeStore] = {}
        self._changes: dict[str, dict[RequirementId, int]] = {}
        self._active: str | None = None

    def snapshot_state(self) -> Any:
        return (
            dict(self._generations),
            {key: index.snapshot_state() for key, index in self._indexes.items()},
            {key: dict(value) for key, value in self._changes.items()},
            self._active,
        )

    def restore_state(self, state: Any) -> None:
        generations, indexes, changes, active = state
        self._generations = dict(generations)
        self._indexes = {}
        for key, snapshot in indexes.items():
            index = InMemoryRequirementKnowledgeStore(self._lock)
            index.restore_state(snapshot)
            self._indexes[key] = index
        self._changes = {key: dict(value) for key, value in changes.items()}
        self._active = active

    def begin_rebuild(self, identity: str) -> IndexGeneration:
        with self._lock:
            for generation in self._generations.values():
                if generation.identity == identity and generation.status == "staging":
                    return generation
            generation = IndexGeneration(str(uuid4()), identity, "staging")
            self._generations[generation.id] = generation
            self._indexes[generation.id] = InMemoryRequirementKnowledgeStore(self._lock)
            self._changes[generation.id] = {}
            return generation

    def list_generations(self) -> tuple[IndexGeneration, ...]:
        with self._lock:
            return tuple(self._generations.values())

    def staging_index(self, generation_id: str) -> RequirementKnowledgeIndexPort:
        return _MemoryGenerationIndex(self, generation_id=generation_id)

    def active_index(self, identity: str) -> RequirementKnowledgeIndexPort:
        return _MemoryGenerationIndex(self, identity=identity)

    def activate(self, generation_id: str) -> None:
        with self._lock:
            if generation_id not in self._generations or self._pending(generation_id, 1):
                raise ModelTransportError("index_required")
            if self._active:
                old = self._generations[self._active]
                self._generations[old.id] = IndexGeneration(old.id, old.identity, "retired")
            generation = self._generations[generation_id]
            self._generations[generation_id] = IndexGeneration(
                generation.id, generation.identity, "active"
            )
            self._active = generation_id

    def _resolve(self, generation_id: str | None, identity: str | None) -> str:
        key = generation_id or self._active
        if key is None or key not in self._generations:
            raise ModelTransportError("index_required")
        if identity is not None and self._generations[key].identity != identity:
            raise ModelTransportError("index_required")
        return key

    def _pending(
        self, key: str, limit: int, after: str = ""
    ) -> tuple[tuple[RequirementId, int], ...]:
        return tuple(
            (requirement_id, change)
            for requirement_id, change in self._sources.source_versions()
            if requirement_id.value > after and self._changes[key].get(requirement_id) != change
        )[:limit]


class _MemoryGenerationIndex:
    def __init__(
        self,
        owner: InMemoryKnowledgeIndexGenerations,
        *,
        generation_id: str | None = None,
        identity: str | None = None,
    ) -> None:
        self._owner = owner
        self._generation_id = generation_id
        self._identity = identity

    def _key(self) -> str:
        return self._owner._resolve(self._generation_id, self._identity)

    def pending_sources(self, limit: int, after: str = "") -> tuple[tuple[RequirementId, int], ...]:
        with self._owner._lock:
            return self._owner._pending(self._key(), limit, after)

    def indexed_fingerprint(self, requirement_id: RequirementId) -> str | None:
        with self._owner._lock:
            return self._owner._indexes[self._key()].indexed_fingerprint(requirement_id)

    def replace_if_current(
        self,
        requirement_id: RequirementId,
        expected_change: int,
        corpus_fingerprint: str,
        chunks: tuple[KnowledgeChunk, ...],
        embeddings: tuple[Embedding, ...],
    ) -> bool:
        with self._owner._lock:
            if dict(self._owner._sources.source_versions()).get(requirement_id) != expected_change:
                return False
            key = self._key()
            self._owner._indexes[key].replace(
                requirement_id, corpus_fingerprint, chunks, embeddings
            )
            self._owner._changes[key][requirement_id] = expected_change
            return True

    def replace(
        self,
        requirement_id: RequirementId,
        corpus_fingerprint: str,
        chunks: tuple[KnowledgeChunk, ...],
        embeddings: tuple[Embedding, ...],
    ) -> None:
        with self._owner._lock:
            change = dict(self._owner._sources.source_versions()).get(requirement_id)
            if change is None or not self.replace_if_current(
                requirement_id, change, corpus_fingerprint, chunks, embeddings
            ):
                raise ModelTransportError("index_required")

    def search(
        self,
        query_text: str,
        query_embedding: Embedding,
        exclude_requirement_id: RequirementId | None,
        limit: int,
    ) -> tuple[KnowledgeMatch, ...]:
        with self._owner._lock:
            return self._owner._indexes[self._key()].search(
                query_text, query_embedding, exclude_requirement_id, limit
            )

    def get_chunks(self, chunk_ids: tuple[str, ...]) -> tuple[KnowledgeChunk, ...]:
        with self._owner._lock:
            return self._owner._indexes[self._key()].get_chunks(chunk_ids)
