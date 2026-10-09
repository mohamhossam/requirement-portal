"""Outbound persistence port for current and historical breakdown state."""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.governance.domain.revision.entities import (
    BreakdownRevision,
    RequirementRevision,
    RevisionNumber,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class BreakdownRepositoryPort(Protocol):
    """Capture and retrieve append-only requirement/breakdown snapshots."""

    def create_current_revisions(self, requirement_id: RequirementId) -> None: ...

    def list_requirement_revisions(
        self, requirement_id: RequirementId
    ) -> list[RequirementRevision]: ...

    def list_breakdown_revisions(
        self, requirement_id: RequirementId
    ) -> list[BreakdownRevision]: ...

    def get_breakdown_revision(
        self, requirement_id: RequirementId, number: RevisionNumber
    ) -> BreakdownRevision | None: ...
