"""Outbound transaction boundary used by delivery interfaces."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol

from smb_requirement_agent.domain.requirement.value_objects import RequirementId


class TransactionManagerPort(Protocol):
    """Provide one atomic unit around an application action."""

    def transaction(self) -> AbstractContextManager[None]: ...

    def mark_rollback_only(self) -> None: ...

    def lock_requirement(self, requirement_id: RequirementId) -> None:
        """Serialize commits that can change one Requirement workspace."""
        ...

    def try_lock_requirement(self, requirement_id: RequirementId) -> bool:
        """Acquire a newly discovered source without waiting while holding another lock."""
        ...

    def external_call(self) -> AbstractContextManager[None]:
        """Suspend transaction ownership while a slow external provider runs."""
        ...
