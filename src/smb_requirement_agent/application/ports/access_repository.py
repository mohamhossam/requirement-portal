"""Persistence boundary for Requirement access and draft ownership."""

from typing import Protocol

from smb_requirement_agent.domain.identity.entities import DraftOwnership, RequirementAccess
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class AccessRepositoryPort(Protocol):
    def get_requirement(self, requirement_id: RequirementId) -> RequirementAccess | None: ...

    def save_requirement(self, access: RequirementAccess) -> None: ...

    def get_draft_ownership(self, draft_id: RequirementId) -> DraftOwnership | None: ...

    def save_draft_ownership(self, ownership: DraftOwnership) -> None: ...

    def delete_draft_ownership(self, draft_id: RequirementId) -> None: ...
