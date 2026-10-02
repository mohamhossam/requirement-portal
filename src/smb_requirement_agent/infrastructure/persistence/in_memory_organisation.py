"""Isolated offline repository for the organisation catalogue."""

from collections.abc import Callable
from threading import RLock

from smb_requirement_agent.application.ports.clock import ClockPort
from smb_requirement_agent.domain.organisation.catalogue import (
    OrganisationAuditEvent,
    OrganisationCatalogue,
)


class InMemoryOrganisationRepository:
    def __init__(self, clock: ClockPort) -> None:
        self._clock = clock
        self._lock = RLock()
        self._catalogue = OrganisationCatalogue()
        self._events: list[OrganisationAuditEvent] = []

    def load(self) -> OrganisationCatalogue:
        with self._lock:
            return self._catalogue

    def change(
        self,
        change: Callable[[OrganisationCatalogue], OrganisationCatalogue],
        actor_id: str,
        action: str,
        subject_id: str,
    ) -> OrganisationCatalogue:
        with self._lock:
            self._catalogue = change(self._catalogue)
            self._events.append(
                OrganisationAuditEvent(actor_id, action, subject_id, self._clock.now())
            )
            return self._catalogue

    def audit(self, limit: int) -> tuple[OrganisationAuditEvent, ...]:
        with self._lock:
            return tuple(reversed(self._events[-limit:]))
