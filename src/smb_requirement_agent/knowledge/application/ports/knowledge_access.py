"""Requirement access for knowledge's automatic work (ADR-0103 Amendment 1, F4).

Knowledge screens, indexes and suggests answers as automatic AI work, so besides identity's
`RequirementAccessPort` it needs the fence for a bound worker attempt. That fence takes jobs'
`AiJobOperation`, which identity cannot import, so knowledge owns this extension of the port.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol

from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementAccessPort,
)
from smb_requirement_agent.jobs.domain.entities import AiJobOperation
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class KnowledgeAccessPort(RequirementAccessPort, Protocol):
    def automatic_mutation(
        self, requirement_id: RequirementId, operation: AiJobOperation
    ) -> AbstractContextManager[None]:
        """The mutation fence for system work: only its bound worker attempt, only while owned."""
        ...
