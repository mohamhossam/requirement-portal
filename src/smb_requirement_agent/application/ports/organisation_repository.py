"""Persistence boundary for the static organisation catalogue."""

from collections.abc import Callable
from typing import Protocol

from smb_requirement_agent.domain.organisation.catalogue import (
    OrganisationAuditEvent,
    OrganisationCatalogue,
)


class OrganisationRepositoryPort(Protocol):
    def load(self) -> OrganisationCatalogue: ...

    def change(
        self,
        change: Callable[[OrganisationCatalogue], OrganisationCatalogue],
        actor_id: str,
        action: str,
        subject_id: str,
    ) -> OrganisationCatalogue:
        """Apply ``change`` to the latest catalogue atomically, audit it, and return the result.

        Concurrent writers are serialised so a change always sees the committed
        state; per-record revisions inside ``change`` detect stale editors.
        """
        ...

    def audit(self, limit: int) -> tuple[OrganisationAuditEvent, ...]: ...
