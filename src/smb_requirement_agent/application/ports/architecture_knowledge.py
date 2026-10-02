"""Port for replaceable SMB architecture knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.domain.architecture.entities import (
    ArchitectureCitation,
    ArchitectureDependency,
    DomainSuggestion,
    JourneyStep,
    ProductContext,
    SystemReference,
)


@dataclass(frozen=True)
class ArchitectureQuery:
    """Provider-neutral evidence used to find likely architecture impact."""

    text: tuple[str, ...]
    declared_systems: tuple[str, ...] = ()
    release_id: str | None = None


@dataclass(frozen=True)
class ArchitectureKnowledgeMatch:
    knowledge_version: str
    systems: tuple[SystemReference, ...]
    dependencies: tuple[ArchitectureDependency, ...]
    citation_ids: tuple[str, ...] = ()
    uncertainty: str | None = None
    model: str | None = None
    embedding_model: str | None = None
    prompt_version: str | None = None
    index_revision: int | None = None
    evidence_classification: str = "legacy_deterministic"
    citations: tuple[ArchitectureCitation, ...] = ()
    adjacent_systems: tuple[SystemReference, ...] = ()
    adjacent_dependencies: tuple[ArchitectureDependency, ...] = ()
    adjacent_omitted: int = 0
    suggested_domains: tuple[DomainSuggestion, ...] = ()
    product_contexts: tuple[ProductContext, ...] = ()
    journey_steps: tuple[JourneyStep, ...] = ()


class ArchitectureKnowledgePort(Protocol):
    def match(self, query: ArchitectureQuery) -> ArchitectureKnowledgeMatch: ...


class ActiveArchitectureReleasePort(Protocol):
    """Which catalogue release new mappings pin. Requirement work reads only its id."""

    def active_release_id(self) -> str: ...


class ArchitectureReleaseStatePort(Protocol):
    """Requirement work's local copy of which catalogue release is active (ADR-0099)."""

    def active_release_id(self) -> str | None: ...

    def apply(self, seq: int, release_id: str) -> None:
        """Record `release_id` unless a newer activation was already applied."""
        ...
