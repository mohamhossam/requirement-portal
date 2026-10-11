"""Sending what a closed Epic delivered to the knowledge service (ontology plan Phase 7).

When a published Epic is closed or removed in the work-item tracker, the tracker's service
hook reaches this portal and the event is queued once, by its event id. A worker reads the
Features' states in the tracker, renders the catalogue change the decided product impact
implies for what was delivered, keeps it, and delivers it to the knowledge service's
`POST /internal/change-requests/deliveries`, retrying until the service answers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

from smb_requirement_agent.references.application.ports.knowledge_handoff import HandoffStatus


class EpicOutcome(StrEnum):
    # Closed as done: what its Features delivered is compared with the prediction.
    CLOSED = "closed"
    # Removed: nothing was delivered, and a closure still waiting is withdrawn.
    REMOVED = "removed"


@dataclass(frozen=True)
class DeliveryClosure:
    """One closed or removed Epic on its way, keyed by the Requirement, the Epic and the
    tracker's event, so the same event delivered twice is queued once."""

    closure_id: str
    requirement_id: str
    epic_external_id: str
    outcome: EpicOutcome
    occurred_at: datetime
    created_at: datetime
    next_attempt_at: datetime
    status: HandoffStatus = HandoffStatus.PENDING
    attempts: int = 0
    lease_token: str | None = None
    lease_until: datetime | None = None
    last_error: str | None = None
    # The rendered body, kept once rendered so every retry sends the same one.
    payload: dict[str, Any] | None = None
    change_request_id: str | None = None
    delivered_at: datetime | None = None
    version: int = 1

    def due(self, now: datetime) -> bool:
        return (
            self.status is HandoffStatus.PENDING
            and self.next_attempt_at <= now
            and (self.lease_until is None or self.lease_until <= now)
        )

    def leased(self, token: str, until: datetime) -> DeliveryClosure:
        return replace(
            self,
            lease_token=token,
            lease_until=until,
            attempts=self.attempts + 1,
            version=self.version + 1,
        )

    def rendered(self, payload: dict[str, Any]) -> DeliveryClosure:
        return replace(self, payload=payload, version=self.version + 1)

    def delivered(self, change_request_id: str | None, at: datetime) -> DeliveryClosure:
        return self._settled(
            HandoffStatus.DELIVERED, None, change_request_id=change_request_id, delivered_at=at
        )

    def skipped(self, reason: str) -> DeliveryClosure:
        return self._settled(HandoffStatus.SKIPPED, reason)

    def failed(self, reason: str) -> DeliveryClosure:
        return self._settled(HandoffStatus.FAILED, reason)

    def retried(self, reason: str, at: datetime) -> DeliveryClosure:
        return replace(
            self,
            next_attempt_at=at,
            lease_token=None,
            lease_until=None,
            last_error=reason,
            version=self.version + 1,
        )

    def _settled(
        self, status: HandoffStatus, reason: str | None, **changes: Any
    ) -> DeliveryClosure:
        return replace(
            self,
            status=status,
            lease_token=None,
            lease_until=None,
            last_error=reason,
            version=self.version + 1,
            **changes,
        )


class DeliveryClosureOutboxPort(Protocol):
    def enqueue(self, closure: DeliveryClosure) -> bool:
        """Queue a closed or removed Epic; False when that event is already queued."""
        ...

    def get(self, closure_id: str) -> DeliveryClosure | None: ...

    def claim(self, now: datetime, lease: timedelta, token: str) -> DeliveryClosure | None:
        """Lease the oldest due closure, or None when nothing is due."""
        ...

    def save(self, closure: DeliveryClosure, expected_version: int) -> None: ...


@dataclass(frozen=True)
class DeliveryReceipt:
    # The catalogue change a closure was kept as; None for a removal.
    change_request_id: str | None
    # The waiting catalogue changes a removal withdrew.
    withdrawn: tuple[str, ...] = ()


class DeliveryInboxPort(Protocol):
    def deliver(self, body: dict[str, Any]) -> DeliveryReceipt:
        """Deliver a closed or removed Epic. Delivering the same closure again changes
        nothing: the service keeps it once by its delivery id."""
        ...
