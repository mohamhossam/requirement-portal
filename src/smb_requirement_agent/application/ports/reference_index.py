"""Version-specific citations and content-specific embedding reuse."""

from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.application.ports.requirement_knowledge import Embedding


@dataclass(frozen=True)
class ReferenceChunk:
    id: str
    document_id: str
    document_title: str
    version_id: str
    version_number: int
    revision_id: str
    publication_id: str
    approval_fingerprint: str
    parent_id: str
    block_id: str
    heading_path: tuple[str, ...]
    location: str
    original_text: str
    search_text: str
    content_hash: str
    language: str
    token_count: int
    chunking_policy: str
    start_offset: int
    end_offset: int
    context_text: str = ""
    context_locations: tuple[str, ...] = ()
    context_token_count: int = 0
    child_strategy: str = "passage"
    field_context: str = ""


class TokenCounterPort(Protocol):
    @property
    def identity(self) -> str: ...
    def count(self, text: str) -> int: ...


class ReferenceIndexPort(Protocol):
    def manifest(self, identity: str, publication_id: str) -> tuple[tuple[str, str], ...]:
        """Sorted (chunk ID, content hash) pairs durably staged for this build."""
        ...

    def cached(self, identity: str, content_hash: str) -> Embedding | None: ...
    def stage(
        self, identity: str, chunks: tuple[ReferenceChunk, ...], vectors: tuple[Embedding, ...]
    ) -> None: ...
    def search(
        self, identity: str, text: str, vector: Embedding, limit: int
    ) -> tuple[ReferenceChunk, ...]: ...
