"""Source-impact decisions on recorded evidence origins.

`SourceLineage` and `merge_lineage` live in the shared kernel (`domain/shared/lineage.py`).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from smb_requirement_agent.domain.document.errors import InvalidDocumentError
from smb_requirement_agent.domain.shared.actors import ActorSnapshot

# MIGRATION SHIM: removed by the import-rewrite commit of PR 2 (ADR-0103).
from smb_requirement_agent.domain.shared.lineage import SourceLineage as SourceLineage
from smb_requirement_agent.domain.shared.lineage import merge_lineage as merge_lineage
from smb_requirement_agent.domain.shared.staleness import require_aware


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
