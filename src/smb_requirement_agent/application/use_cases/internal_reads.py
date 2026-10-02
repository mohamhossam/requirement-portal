"""What requirement work answers for the knowledge service over /internal (ADR-0099).

The knowledge service authenticates as a service; the person it acts for is named
by id. Every read here keeps the same privacy as the in-process read it
replaces: a document owner sees dependents only on Requirements they may see,
and mapping statistics are counts, never which Requirements.
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.application.ports.actor_directory import ActorDirectoryPort
from smb_requirement_agent.application.ports.architecture_mapping_stats import (
    ArchitectureMappingStatsPort,
    MappingCount,
)
from smb_requirement_agent.application.ports.source_dependencies import (
    SourceDependency,
    SourceDependencyPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.source_impact import (
    DependencyImpactPage,
    SourceImpactReview,
)
from smb_requirement_agent.domain.identity.entities import ActorId, ActorProfile


@dataclass(frozen=True)
class DependentsPage:
    items: tuple[SourceDependency, ...]
    next_offset: int | None


class InternalReads:
    def __init__(
        self,
        dependencies: SourceDependencyPort,
        impact: SourceImpactReview,
        actors: ActorDirectoryPort,
        mapping_stats: ArchitectureMappingStatsPort,
        transactions: TransactionManagerPort,
    ) -> None:
        self._dependencies = dependencies
        self._impact = impact
        self._actors = actors
        self._mapping_stats = mapping_stats
        self._transactions = transactions

    def document_impact(
        self,
        document_id: str,
        actor_id: str,
        *,
        active_only: bool,
        query: str,
        offset: int,
        limit: int,
    ) -> DependencyImpactPage:
        """A document owner's impact view; ownership is checked again against the local copy."""
        return self._impact.page(
            _acting(actor_id),
            document_id=document_id,
            active_only=active_only,
            query=query,
            offset=offset,
            limit=limit,
        )

    def dependents(
        self, document_id: str, actor_id: str, target_kind: str | None, offset: int, limit: int
    ) -> DependentsPage:
        with self._transactions.transaction():
            rows = self._dependencies.page(
                ActorId(actor_id),
                document_id=document_id,
                target_kind=target_kind,
                offset=offset,
                limit=limit + 1,
            )
        return DependentsPage(rows[:limit], offset + limit if len(rows) > limit else None)

    def mapping_counts(self) -> tuple[MappingCount, ...]:
        return self._mapping_stats.by_release()

    def actor(self, actor_id: str) -> ActorProfile | None:
        return self._actors.get(ActorId(actor_id))


def _acting(actor_id: str) -> ActorProfile:
    """The person the knowledge service acts for: rights are checked by identity alone."""
    return ActorProfile(ActorId(actor_id), actor_id)
