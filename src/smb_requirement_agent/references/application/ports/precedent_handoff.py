"""Sending decided product verdicts to the knowledge service (ontology plan Phase 5).

When a Requirement Owner accepts, overrides or marks unknown the suggested product
impact, the decision is queued in the decision's own transaction, already rendered as the
precedent the knowledge service keeps. A worker delivers it to
`POST /internal/architecture/precedents`, retrying until the service answers. The next
assessment there shows the nearest decided requirements as worked examples, and a
knowledge admin sees how often suggestions were changed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Protocol

from smb_requirement_agent.references.application.ports.knowledge_handoff import HandoffStatus


@dataclass(frozen=True)
class PrecedentHandoff:
    """One decision on its way, keyed by the analysis and its version: deciding again
    queues another, and the knowledge service keeps the later one."""

    handoff_id: str
    requirement_id: str
    # The precedent as the contract describes it, rendered when the decision was made.
    payload: dict[str, Any]
    created_at: datetime
    next_attempt_at: datetime
    status: HandoffStatus = HandoffStatus.PENDING
    attempts: int = 0
    lease_token: str | None = None
    lease_until: datetime | None = None
    last_error: str | None = None
    delivered_at: datetime | None = None
    version: int = 1

    def due(self, now: datetime) -> bool:
        return (
            self.status is HandoffStatus.PENDING
            and self.next_attempt_at <= now
            and (self.lease_until is None or self.lease_until <= now)
        )

    def leased(self, token: str, until: datetime) -> PrecedentHandoff:
        return replace(
            self,
            lease_token=token,
            lease_until=until,
            attempts=self.attempts + 1,
            version=self.version + 1,
        )

    def delivered(self, at: datetime) -> PrecedentHandoff:
        return self._settled(HandoffStatus.DELIVERED, None, delivered_at=at)

    def failed(self, reason: str) -> PrecedentHandoff:
        return self._settled(HandoffStatus.FAILED, reason)

    def retried(self, reason: str, at: datetime) -> PrecedentHandoff:
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
    ) -> PrecedentHandoff:
        return replace(
            self,
            status=status,
            lease_token=None,
            lease_until=None,
            last_error=reason,
            version=self.version + 1,
            **changes,
        )


class PrecedentOutboxPort(Protocol):
    def enqueue(self, handoff: PrecedentHandoff) -> bool:
        """Queue a decision inside the caller's transaction; False when that analysis
        version is already queued."""
        ...

    def get(self, handoff_id: str) -> PrecedentHandoff | None: ...

    def claim(self, now: datetime, lease: timedelta, token: str) -> PrecedentHandoff | None:
        """Lease the oldest due decision, or None when nothing is due."""
        ...

    def save(self, handoff: PrecedentHandoff, expected_version: int) -> None: ...


class PrecedentInboxPort(Protocol):
    def record(self, precedent: dict[str, Any]) -> bool:
        """Deliver a decision; whether the service kept it (False: it already holds this
        decision or a later one). Delivering the same decision again changes nothing."""
        ...
