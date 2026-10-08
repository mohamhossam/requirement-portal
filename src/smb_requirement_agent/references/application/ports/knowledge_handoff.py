"""Handing approved backlogs to the knowledge service (ADR-0101 Amendment 2).

A breakdown's final approval enqueues a handoff in the approval's own transaction. A worker
later renders that approval's revision as the neutral backlog export and delivers it to the
knowledge service's change-request inbox, retrying until the inbox answers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol


class HandoffStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    # The approval's revision is not exportable (or no longer there); nothing is sent.
    SKIPPED = "skipped"
    # The inbox refused it, or every attempt failed; logged, never retried on its own.
    FAILED = "failed"


@dataclass(frozen=True)
class BacklogHandoff:
    """One final approval on its way to the knowledge service, keyed by the approval."""

    approval_id: str
    requirement_id: str
    subject_fingerprint: str
    created_at: datetime
    next_attempt_at: datetime
    status: HandoffStatus = HandoffStatus.PENDING
    attempts: int = 0
    lease_token: str | None = None
    lease_until: datetime | None = None
    last_error: str | None = None
    # The rendered export, kept once rendered so every retry sends the same body.
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

    def leased(self, token: str, until: datetime) -> BacklogHandoff:
        return replace(
            self,
            lease_token=token,
            lease_until=until,
            attempts=self.attempts + 1,
            version=self.version + 1,
        )

    def rendered(self, payload: dict[str, Any]) -> BacklogHandoff:
        return replace(self, payload=payload, version=self.version + 1)

    def delivered(self, change_request_id: str, at: datetime) -> BacklogHandoff:
        return self._settled(
            HandoffStatus.DELIVERED, None, change_request_id=change_request_id, delivered_at=at
        )

    def skipped(self, reason: str) -> BacklogHandoff:
        return self._settled(HandoffStatus.SKIPPED, reason)

    def failed(self, reason: str) -> BacklogHandoff:
        return self._settled(HandoffStatus.FAILED, reason)

    def retried(self, reason: str, at: datetime) -> BacklogHandoff:
        return replace(
            self,
            next_attempt_at=at,
            lease_token=None,
            lease_until=None,
            last_error=reason,
            version=self.version + 1,
        )

    def _settled(self, status: HandoffStatus, reason: str | None, **changes: Any) -> BacklogHandoff:
        return replace(
            self,
            status=status,
            lease_token=None,
            lease_until=None,
            last_error=reason,
            version=self.version + 1,
            **changes,
        )


class ApprovedBacklogOutboxPort(Protocol):
    def enqueue(self, handoff: BacklogHandoff) -> bool:
        """Queue a handoff inside the caller's transaction; False when that approval is
        already queued."""
        ...

    def get(self, approval_id: str) -> BacklogHandoff | None: ...

    def claim(self, now: datetime, lease: timedelta, token: str) -> BacklogHandoff | None:
        """Lease the oldest due handoff, or None when nothing is due."""
        ...

    def save(self, handoff: BacklogHandoff, expected_version: int) -> None: ...


class ChangeRequestInboxPort(Protocol):
    def deliver(self, export: dict[str, Any]) -> str:
        """Deliver an approved-backlog export; the change request it became. Delivering the
        same approval again answers the same change request."""
        ...
