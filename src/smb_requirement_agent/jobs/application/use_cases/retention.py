"""Operational data retention (ADR-0079).

Only read notifications are pruned. AI jobs are kept: they are the activity
feed's record of AI work and the memory the automatic-screen reservation
relies on. Unread notifications are kept until they are read; the list is
bounded when it is read instead.
"""

from __future__ import annotations

from datetime import timedelta

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.jobs.application.ports.notifications import NotificationRepositoryPort


class PruneReadNotifications:
    def __init__(self, notifications: NotificationRepositoryPort, clock: ClockPort) -> None:
        self._notifications = notifications
        self._clock = clock

    def execute(self, retention: timedelta) -> int:
        """Delete notifications read longer ago than `retention`; return how many."""
        if retention <= timedelta(0):
            raise ValueError("Notification retention must be a positive period.")
        return self._notifications.delete_read_before(self._clock.now() - retention)
