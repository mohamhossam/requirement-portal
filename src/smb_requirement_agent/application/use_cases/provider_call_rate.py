"""A per-actor ceiling on operations that call an AI provider."""

from __future__ import annotations

import itertools
import math
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import ProviderRateLimitExceededError
from smb_requirement_agent.shared_kernel.actors import ActorProfile

_WINDOW = timedelta(minutes=1)


@dataclass(frozen=True)
class ProviderCallTicket:
    """One counted call, so it can be refunded if the operation never ran.

    The sequence number keeps two calls counted at the same instant distinct.
    """

    actor_key: str
    at: datetime
    sequence: int


class ProviderCallRateLimit:
    """Caps how many provider-calling operations one actor may start per minute.

    Every provider call spends money and shared model capacity, and nothing else
    stops one retry loop or script from spending all of it. The window slides,
    so a burst is refused until its oldest call is a minute old.

    Counts live in this process. Behind several API replicas an actor's ceiling
    is the per-replica limit times the replica count; a gateway limit is the
    place for an exact global ceiling. A limit of 0 disables the check.
    """

    def __init__(self, limit_per_minute: int, clock: ClockPort) -> None:
        if limit_per_minute < 0:
            raise ValueError("The provider call limit must not be negative.")
        self._limit = limit_per_minute
        self._clock = clock
        self._lock = threading.Lock()
        self._calls: dict[str, deque[tuple[datetime, int]]] = {}
        self._sequence = itertools.count()

    def acquire(self, actor: ActorProfile) -> ProviderCallTicket | None:
        """Record one provider-calling operation, or refuse it with a retry delay.

        Returns the ticket that `refund` takes back, or None when unlimited.
        """
        if self._limit == 0:
            return None
        now = self._clock.now()
        key = actor.id.value
        with self._lock:
            calls = self._calls.setdefault(key, deque())
            while calls and now - calls[0][0] >= _WINDOW:
                calls.popleft()
            if len(calls) >= self._limit:
                oldest = calls[0][0]
                retry_after = max(1, math.ceil((oldest + _WINDOW - now).total_seconds()))
                raise ProviderRateLimitExceededError(
                    f"Too many AI requests: at most {self._limit} per minute. "
                    "Creating or changing a Requirement counts, because it starts "
                    "knowledge screening. "
                    f"Try again in {retry_after} seconds.",
                    retry_after_seconds=retry_after,
                )
            ticket = ProviderCallTicket(key, now, next(self._sequence))
            calls.append((ticket.at, ticket.sequence))
            self._forget_idle(now)
        return ticket

    def refund(self, ticket: ProviderCallTicket) -> None:
        """Return a call the operation never spent, such as a request refused as invalid."""
        with self._lock:
            calls = self._calls.get(ticket.actor_key)
            entry = (ticket.at, ticket.sequence)
            if calls is not None and entry in calls:
                calls.remove(entry)

    def _forget_idle(self, now: datetime) -> None:
        # A refund can leave an actor with no calls at all; that is idle too.
        idle = [
            key for key, calls in self._calls.items() if not calls or now - calls[-1][0] >= _WINDOW
        ]
        for key in idle:
            del self._calls[key]
