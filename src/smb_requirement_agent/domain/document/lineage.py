"""Recorded evidence origins, independent of wording and retrieval similarity."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from smb_requirement_agent.domain.document.errors import InvalidDocumentError
from smb_requirement_agent.domain.document.reference import PublishedReference
from smb_requirement_agent.domain.identity.entities import ActorSnapshot
from smb_requirement_agent.domain.shared.staleness import require_aware


@dataclass(frozen=True)
class SourceLineage:
    citation: PublishedReference
    via: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if any(not step.strip() for step in self.via):
            raise InvalidDocumentError("Evidence lineage steps cannot be blank.")

    def through(self, source: str) -> "SourceLineage":
        return replace(self, via=(*self.via, source))


def merge_lineage(*groups: tuple[SourceLineage, ...]) -> tuple[SourceLineage, ...]:
    return tuple(dict.fromkeys(item for group in groups for item in group))


class ImpactDecisionKind(StrEnum):
    RETAIN = "retain_historical"
    REVISE = "revise_content"


@dataclass(frozen=True)
class ImpactDecision:
    dependency_id: str
    publication_state: str
    decision: ImpactDecisionKind
    reason: str
    actor: ActorSnapshot
    recorded_at: datetime
    version: int

    def __post_init__(self) -> None:
        if not self.reason.strip() or self.version < 1:
            raise InvalidDocumentError("Impact review requires a reason and positive version.")
        require_aware(self.recorded_at, "impact decision recorded_at")
