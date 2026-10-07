"""What requirement work answers for the knowledge service over /internal (ADR-0099).

The knowledge service authenticates as a service; the person it acts for is named
by id. Every read here keeps the same privacy as the in-process read it
replaces: a document owner sees dependents only on Requirements they may see,
and mapping statistics, citation counts and the corpus summary are counts, never which
Requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.corpus_summary import CorpusCountsPort
from smb_requirement_agent.application.ports.source_dependencies import (
    SourceDependency,
    SourceDependencyPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.requirement_indexing import IndexBacklogReader
from smb_requirement_agent.application.use_cases.source_impact import (
    DependencyImpactPage,
    SourceImpactReview,
)
from smb_requirement_agent.breakdown.application.ports.architecture_mapping_stats import (
    ArchitectureMappingStatsPort,
    MappingCount,
)
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
)


@dataclass(frozen=True)
class DependentsPage:
    items: tuple[SourceDependency, ...]
    next_offset: int | None


@dataclass(frozen=True)
class OpenFindingAges:
    """Findings still in force, by how long ago they were raised."""

    under_7_days: int
    from_7_to_30_days: int
    over_30_days: int


@dataclass(frozen=True)
class CorpusSummary:
    """The Requirement knowledge corpus's health for the Knowledge Center (A′)."""

    # Every Requirement, including those closed as duplicates.
    requirements: int
    # Closed as duplicates: kept in the index with no passages.
    duplicates: int
    # Retired from the corpus by a knowledge admin: readable, but kept out of screening.
    retired: int
    # Indexed at their latest change.
    current: int
    # Changed and not yet indexed again.
    waiting: int
    # Stopped retrying after repeated failures, until someone retries them.
    failed: int
    # The embedding model changed and the index must be rebuilt before anything else.
    rebuild_required: bool
    open_findings: OpenFindingAges
    as_of: datetime


class InternalReads:
    def __init__(
        self,
        dependencies: SourceDependencyPort,
        impact: SourceImpactReview,
        mapping_stats: ArchitectureMappingStatsPort,
        transactions: TransactionManagerPort,
        corpus: CorpusCountsPort,
        backlog: IndexBacklogReader,
        clock: ClockPort,
    ) -> None:
        self._dependencies = dependencies
        self._impact = impact
        self._mapping_stats = mapping_stats
        self._transactions = transactions
        self._corpus = corpus
        self._backlog = backlog
        self._clock = clock

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

    def citation_counts(self, document_ids: tuple[str, ...]) -> dict[str, int]:
        """Requirements citing each library document now, counted across the portfolio."""
        with self._transactions.transaction():
            return self._dependencies.citation_counts(tuple(dict.fromkeys(document_ids)))

    def mapping_counts(self) -> tuple[MappingCount, ...]:
        return self._mapping_stats.by_release()

    def corpus_summary(self) -> CorpusSummary:
        counts = self._corpus.counts()
        backlog = self._backlog.backlog()
        now = self._clock.now()
        ages = [now - raised for raised in counts.open_findings_raised_at]
        return CorpusSummary(
            requirements=counts.requirements,
            duplicates=counts.duplicates,
            retired=counts.retired,
            # Retired Requirements have left the corpus: they are none of current, waiting, failed.
            current=max(0, counts.requirements - counts.retired - backlog.waiting - backlog.failed),
            waiting=backlog.waiting,
            failed=backlog.failed,
            rebuild_required=backlog.rebuild_required,
            open_findings=OpenFindingAges(
                under_7_days=sum(1 for age in ages if age < timedelta(days=7)),
                from_7_to_30_days=sum(
                    1 for age in ages if timedelta(days=7) <= age <= timedelta(days=30)
                ),
                over_30_days=sum(1 for age in ages if age > timedelta(days=30)),
            ),
            as_of=now,
        )


def _acting(actor_id: str) -> ActorProfile:
    """The person the knowledge service acts for: rights are checked by identity alone."""
    return ActorProfile(ActorId(actor_id), actor_id)
