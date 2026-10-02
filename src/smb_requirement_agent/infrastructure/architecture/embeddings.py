"""Architecture evidence embeddings from the application's configured embedding model."""

from __future__ import annotations

import hashlib
import math

from smb_requirement_agent.application.errors import KnowledgeGenerationError, ModelTransportError
from smb_requirement_agent.application.ports.architecture_rag import ArchitectureEvidenceError
from smb_requirement_agent.application.ports.requirement_knowledge import KnowledgeEmbeddingPort

DIMENSIONS = 768
BATCH_SIZE = 32


class FakeEmbeddings:
    """Deterministic bag-of-words vectors for offline tests."""

    @property
    def model(self) -> str:
        return "fake-architecture-embedding-v2"

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        vectors: list[tuple[float, ...]] = []
        for value in texts:
            buckets = [0.0] * DIMENSIONS
            for word in value.casefold().split():
                digest = hashlib.sha256(word.encode("utf-8")).digest()
                buckets[int.from_bytes(digest[:2], "big") % DIMENSIONS] += 1.0
            norm = math.sqrt(sum(item * item for item in buckets)) or 1.0
            vectors.append(tuple(item / norm for item in buckets))
        return tuple(vectors)


class ArchitectureEmbeddings:
    """The embedding model every other knowledge feature uses, in bounded batches.

    Requirement knowledge and the document library already embed through this
    port, so architecture evidence follows the same provider, credentials and
    residency choice instead of a separate local-only endpoint.
    """

    def __init__(self, embeddings: KnowledgeEmbeddingPort, batch_size: int = BATCH_SIZE) -> None:
        self._embeddings = embeddings
        self._batch_size = batch_size

    @property
    def model(self) -> str:
        return self._embeddings.model

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        vectors: list[tuple[float, ...]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            try:
                values = self._embeddings.embed(batch)
            except (ModelTransportError, KnowledgeGenerationError) as exc:
                raise ArchitectureEvidenceError(
                    "The embedding service returned unusable output."
                ) from exc
            if len(values) != len(batch) or any(
                len(vector) != DIMENSIONS
                or not all(math.isfinite(x) for x in vector)
                or not any(x != 0 for x in vector)
                for vector in values
            ):
                raise ArchitectureEvidenceError(
                    f"The embedding service must return one {DIMENSIONS}-dimensional vector "
                    "per passage."
                )
            vectors.extend(tuple(float(x) for x in vector) for vector in values)
        return tuple(vectors)
