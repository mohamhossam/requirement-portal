"""Operational data retention (ADR-0079).

Read notifications are deleted after their period. AI job rows are kept: they
are the activity feed's record of AI work. Only the stored inputs of succeeded
and cancelled jobs are cleared after theirs (the ADR-0079 amendment); knowledge
screens keep their inputs, which the automatic-screen reservation relies on.
Unread notifications are kept until they are read; the list is bounded when it
is read instead.
"""

from __future__ import annotations

from datetime import timedelta

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobRetentionPort
from smb_requirement_agent.jobs.application.ports.notifications import NotificationRepositoryPort

PAYLOAD_PRUNE_BATCH = 500


class PruneReadNotifications:
    def __init__(self, notifications: NotificationRepositoryPort, clock: ClockPort) -> None:
        self._notifications = notifications
        self._clock = clock

    def execute(self, retention: timedelta) -> int:
        """Delete notifications read longer ago than `retention`; return how many."""
        if retention <= timedelta(0):
            raise ValueError("Notification retention must be a positive period.")
        return self._notifications.delete_read_before(self._clock.now() - retention)


class PruneFinishedJobPayloads:
    def __init__(self, jobs: AiJobRetentionPort, clock: ClockPort) -> None:
        self._jobs = jobs
        self._clock = clock

    def execute(self, retention: timedelta) -> int:
        """Clear the inputs of jobs finished longer ago than `retention`; return how many."""
        if retention <= timedelta(0):
            raise ValueError("AI job payload retention must be a positive period.")
        return self._jobs.prune_finished_inputs(self._clock.now() - retention, PAYLOAD_PRUNE_BATCH)
