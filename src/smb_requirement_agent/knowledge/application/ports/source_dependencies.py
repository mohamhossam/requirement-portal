"""Maintained reverse evidence index and append-only impact decisions."""

from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.knowledge.domain.lineage import ImpactDecision
from smb_requirement_agent.shared_kernel.actors import ActorId
from smb_requirement_agent.shared_kernel.lineage import SourceLineage


@dataclass(frozen=True)
class SourceDependency:
    id: str
    requirement_id: str
    requirement_title: str
    target_kind: str
    target_id: str
    statement: str
    content_fingerprint: str
    lineage: SourceLineage
    active: bool
    current: bool = True
    status: str = "recorded"
    analysis_id: str | None = None
    round_number: int | None = None


class SourceDependencyPort(Protocol):
    def replace_current(self, requirement_id: str, rows: tuple[SourceDependency, ...]) -> None: ...
    def get(self, dependency_id: str) -> SourceDependency | None: ...
    def page(
        self,
        actor_id: ActorId,
        *,
        document_id: str | None = None,
        requirement_id: str | None = None,
        active_only: bool = False,
        target_kind: str | None = None,
        query: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[SourceDependency, ...]: ...
    def for_requirement(self, requirement_id: str) -> tuple[SourceDependency, ...]: ...
    def citation_counts(self, document_ids: tuple[str, ...]) -> dict[str, int]:
        """How many Requirements currently cite each document, across the portfolio."""
        ...

    def decisions(self, dependency_id: str) -> tuple[ImpactDecision, ...]: ...
    def decide(self, decision: ImpactDecision, expected_version: int) -> None: ...
