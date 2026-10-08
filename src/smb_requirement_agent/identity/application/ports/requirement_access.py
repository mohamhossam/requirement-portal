"""Requirement-scoped access, as the other contexts check it (ADR-0103 Amendment 1, F4).

Every context authorizes Requirement-scoped work through this port, which identity publishes.
Workflows' `RequirementAccessService` implements it: it reads Requirements, drafts, question
assignees and the running job, so it cannot live in identity itself.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from enum import Enum
from typing import Protocol

from smb_requirement_agent.identity.domain.entities import DraftOwnership, RequirementAccess
from smb_requirement_agent.shared_kernel.actors import ActorId, ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class RequirementPermission(Enum):
    """What a Requirement-scoped action needs: any current member, or the owner."""

    MEMBER = "member"
    OWNER = "owner"


class RequirementAccessPort(Protocol):
    def require(
        self,
        requirement_id: RequirementId,
        current: ActorProfile,
        permission: RequirementPermission,
    ) -> RequirementAccess:
        """Check current access, for a caller already inside the Requirement's unit of work."""
        ...

    def require_requirement_member(
        self, requirement_id: RequirementId, current: ActorProfile
    ) -> RequirementAccess:
        """Authorize a Requirement mutation shared by the owner and reviewers."""
        ...

    def require_answerer(
        self,
        requirement_id: RequirementId,
        current: ActorProfile,
        assignee: ActorId | None,
        *,
        allow_team: bool,
    ) -> None:
        """Authorize answering a clarification question."""
        ...

    def require_owner_of_either(
        self, first: RequirementId, second: RequirementId, current: ActorProfile
    ) -> None:
        """Authorize an action shared by the owners of two linked Requirements."""
        ...

    def mutation(
        self,
        requirement_id: RequirementId,
        current: ActorProfile,
        permission: RequirementPermission,
    ) -> AbstractContextManager[None]:
        """Run a mutation authorized on both sides of any provider I/O it performs."""
        ...

    def execute_mutation[T](
        self,
        requirement_id: RequirementId,
        current: ActorProfile,
        permission: RequirementPermission,
        operation: Callable[[], T],
    ) -> T:
        """`mutation` for callers holding the work as a callable."""
        ...

    def create_requirement_owner(
        self, requirement_id: RequirementId, actor: ActorProfile
    ) -> RequirementAccess:
        """Record the creator as a new Requirement's owner."""
        ...

    def create_draft_owner(self, draft_id: RequirementId, actor: ActorProfile) -> DraftOwnership:
        """Record the creator as a new draft's owner."""
        ...

    def require_draft_owner(self, draft_id: RequirementId, current: ActorProfile) -> DraftOwnership:
        """Authorize work on a draft by its owner."""
        ...

    def can_access_draft(self, draft_id: RequirementId, current: ActorProfile) -> bool:
        """Whether the actor owns the draft."""
        ...
