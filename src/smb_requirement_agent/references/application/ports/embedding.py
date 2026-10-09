"""Text-model ports both the requirement and the knowledge side use.

They name no corpus and no retrieval behaviour, so they sit outside both
contexts (ADR-0099). The vector value itself is platform-kernel's.
"""

from typing import Protocol

from smb_kernel.embeddings import Embedding


class KnowledgeEmbeddingPort(Protocol):
    model: str

    def embed(self, texts: tuple[str, ...]) -> tuple[Embedding, ...]: ...


class TokenCounterPort(Protocol):
    @property
    def identity(self) -> str: ...
    def count(self, text: str) -> int: ...
