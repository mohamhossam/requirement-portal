"""Reviewable architecture references attached to backlog items."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from smb_requirement_agent.domain.architecture.catalogue import (
    ArchitectureCitation,
    ArchitectureDependency,
    DomainSuggestion,
    InvalidArchitectureContentError,
    JourneyStep,
    ProductContext,
    SystemReference,
)
from smb_requirement_agent.shared_kernel.staleness import require_aware


def _text(value: str, field: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise InvalidArchitectureContentError(f"Architecture {field} must not be blank.")
    return stripped


def _check_adjacent(
    mapped: set[str],
    systems: tuple[SystemReference, ...],
    dependencies: tuple[ArchitectureDependency, ...],
) -> None:
    """Connected systems sit outside the mapping and each is reached by a relationship."""
    ids = [item.id for item in systems]
    if len(ids) != len(set(ids)) or mapped & set(ids):
        raise InvalidArchitectureContentError(
            "Connected systems must be unique and not already mapped."
        )
    adjacent_ids = set(ids)
    reached: set[str] = set()
    for item in dependencies:
        ends = {item.source_system_id, item.target_system_id}
        if len(ends & mapped) != 1 or len(ends & adjacent_ids) != 1:
            raise InvalidArchitectureContentError(
                "A connected-system dependency must join a mapped and a connected system."
            )
        reached |= ends & adjacent_ids
    if reached != adjacent_ids:
        raise InvalidArchitectureContentError(
            "Every connected system needs the relationship that connects it."
        )


@dataclass(frozen=True)
class ArchitectureImpact:
    knowledge_version: str
    mapped_at: datetime
    systems: tuple[SystemReference, ...]
    dependencies: tuple[ArchitectureDependency, ...] = ()
    citation_ids: tuple[str, ...] = ()
    uncertainty: str | None = None
    model: str | None = None
    embedding_model: str | None = None
    prompt_version: str | None = None
    index_revision: int | None = None
    evidence_classification: str = "legacy_deterministic"
    citations: tuple[ArchitectureCitation, ...] = ()
    # Systems one catalogued relationship away from the mapped ones. They are
    # listed for a reviewer to check, never counted as mapped.
    adjacent_systems: tuple[SystemReference, ...] = ()
    adjacent_dependencies: tuple[ArchitectureDependency, ...] = ()
    adjacent_omitted: int = 0
    # Capability domains the item's wording matched, offered only when no
    # catalogued system was mapped (ADR-0089).
    suggested_domains: tuple[DomainSuggestion, ...] = ()
    # Product offerings the item names, and the journey steps of its mapped
    # systems: advice for a reviewer, never mapped impact (ADR-0097).
    product_contexts: tuple[ProductContext, ...] = ()
    journey_steps: tuple[JourneyStep, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "knowledge_version", _text(self.knowledge_version, "version"))
        require_aware(self.mapped_at, "architecture mapped_at")
        system_ids = [item.id for item in self.systems]
        if len(system_ids) != len(set(system_ids)):
            raise InvalidArchitectureContentError("Mapped systems must have unique ids.")
        known = set(system_ids)
        if any(
            item.system_id not in known or item.chunk_id not in self.citation_ids
            for item in self.citations
        ):
            raise InvalidArchitectureContentError(
                "Citations must reference mapped systems and evidence."
            )
        if any(
            item.source_system_id not in known or item.target_system_id not in known
            for item in self.dependencies
        ):
            raise InvalidArchitectureContentError(
                "Architecture dependencies must connect systems in the impact."
            )
        if any(not item.strip() for item in self.citation_ids):
            raise InvalidArchitectureContentError("Architecture citations must not be blank.")
        if self.evidence_classification not in {"legacy_deterministic", "ai_inference"}:
            raise InvalidArchitectureContentError(
                "Architecture evidence classification is invalid."
            )
        _check_adjacent(known, self.adjacent_systems, self.adjacent_dependencies)
        if self.suggested_domains and any(item.catalogued for item in self.systems):
            raise InvalidArchitectureContentError(
                "Domain suggestions are only for an item with no catalogued system."
            )
        if self.adjacent_omitted < 0:
            raise InvalidArchitectureContentError("Omitted connected systems cannot be negative.")
        if any(item.system_id not in known for item in self.journey_steps):
            raise InvalidArchitectureContentError("Journey steps must be of mapped systems.")

    @property
    def cross_system(self) -> bool:
        return len(self.systems) > 1
