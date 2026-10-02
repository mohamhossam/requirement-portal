"""Replaceable evidence index and reasoning boundaries for architecture mapping."""

from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.application.ports.architecture_knowledge import ArchitectureQuery
from smb_requirement_agent.domain.architecture.entities import ArchitectureCitation
from smb_requirement_agent.domain.architecture.knowledge import ArchitectureKnowledge


@dataclass(frozen=True)
class EvidenceChunk:
    id: str
    source_label: str
    location: str
    text: str
    document_version_id: str | None = None


@dataclass(frozen=True)
class EvidenceSelection:
    system_ids: tuple[str, ...]
    citation_ids: tuple[str, ...]
    uncertainty: str | None = None
    citations: tuple[ArchitectureCitation, ...] = ()


class ArchitectureEvidenceIndexPort(Protocol):
    @property
    def embedding_model(self) -> str: ...

    @property
    def profile(self) -> str: ...

    def store(self, release_id: str, index_id: str, chunks: tuple[EvidenceChunk, ...]) -> None: ...

    def retrieve(self, release_id: str, query: str, limit: int) -> tuple[EvidenceChunk, ...]: ...

    def get(self, release_id: str, chunk_id: str) -> EvidenceChunk | None: ...

    def system_chunk(self, index_id: str, system_id: str) -> EvidenceChunk | None:
        """The first indexed chunk of one catalogue system's own record."""
        ...


class ArchitectureReasonerPort(Protocol):
    @property
    def model(self) -> str: ...

    def select(
        self,
        query: ArchitectureQuery,
        release: ArchitectureKnowledge,
        evidence: tuple[EvidenceChunk, ...],
    ) -> EvidenceSelection: ...


class EmbeddingPort(Protocol):
    @property
    def model(self) -> str: ...

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...


class ArchitectureEvidenceError(Exception):
    """A local embedding or reasoning provider returned unusable evidence."""
