"""A per-actor ceiling on operations that call an AI provider, and a daily token budget."""

from __future__ import annotations

import math
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.jobs.application.errors import (
    ProviderBudgetExhaustedError,
    ProviderRateLimitExceededError,
)
from smb_requirement_agent.jobs.application.ports.provider_calls import (
    ProviderCallLogPort,
    ProviderSpendPort,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile

_WINDOW = timedelta(minutes=1)


@dataclass(frozen=True)
class ProviderCallTicket:
    """One counted call, so it can be refunded if the operation never ran."""

    actor_key: str
    call_id: str


class ProviderCallRateLimit:
    """Caps how many provider-calling operations one actor may start per minute.

    Every provider call spends money and shared model capacity, and nothing else
    stops one retry loop or script from spending all of it. The window slides,
    so a burst is refused until its oldest call is a minute old.

    The log decides how far the count reaches: in PostgreSQL it is shared by every
    API replica, so the ceiling holds across all of them (ADR-0106). A limit of 0
    disables the check.
    """

    def __init__(self, limit_per_minute: int, clock: ClockPort, log: ProviderCallLogPort) -> None:
        if limit_per_minute < 0:
            raise ValueError("The provider call limit must not be negative.")
        self._limit = limit_per_minute
        self._clock = clock
        self._log = log

    def acquire(self, actor: ActorProfile) -> ProviderCallTicket | None:
        """Record one provider-calling operation, or refuse it with a retry delay.

        Returns the ticket that `refund` takes back, or None when unlimited.
        """
        if self._limit == 0:
            return None
        now = self._clock.now()
        ticket = ProviderCallTicket(actor.id.value, str(uuid.uuid4()))
        oldest = self._log.record_unless_full(
            ticket.actor_key, ticket.call_id, now, _WINDOW, self._limit
        )
        if oldest is not None:
            retry_after = max(1, math.ceil((oldest + _WINDOW - now).total_seconds()))
            raise ProviderRateLimitExceededError(
                f"Too many AI requests: at most {self._limit} per minute. "
                "Creating or changing a Requirement counts, because it starts "
                "knowledge screening. "
                f"Try again in {retry_after} seconds.",
                retry_after_seconds=retry_after,
            )
        return ticket

    def refund(self, ticket: ProviderCallTicket) -> None:
        """Return a call the operation never spent, such as a request refused as invalid."""
        self._log.remove(ticket.actor_key, ticket.call_id)


class ProviderSpendBudget:
    """The tokens the providers may spend per UTC day, across every process (ADR-0106).

    Spend is what the providers report, recorded as each response arrives. Once
    the day's budget is spent, new AI work is refused and queued jobs wait for the
    next day; calls already under way finish, so a day can overshoot by them.
    A budget of 0 records spend without limiting it.

    `held_back` is told each time work is held back, with `start` for a refused
    start and `claim` for a claim a worker skipped, for the spend-blocked metric.
    """

    def __init__(
        self,
        daily_tokens: int,
        clock: ClockPort,
        spend: ProviderSpendPort,
        held_back: Callable[[str], None],
    ) -> None:
        if daily_tokens < 0:
            raise ValueError("The daily token budget must not be negative.")
        self._daily = daily_tokens
        self._clock = clock
        self._spend = spend
        self._held_back = held_back

    def record(self, tokens: int) -> None:
        if tokens > 0:
            self._spend.add(self._today(), tokens)

    def exhausted(self) -> bool:
        return self._daily > 0 and self._spend.spent(self._today()) >= self._daily

    def admits_claim(self) -> bool:
        """Whether a worker may claim a queued job now; while the budget is spent, it may not."""
        if not self.exhausted():
            return True
        self._held_back("claim")
        return False

    def require_available(self) -> None:
        """Refuse new AI work once today's budget is spent, saying when it resets."""
        if not self.exhausted():
            return
        self._held_back("start")
        now = self._clock.now().astimezone(UTC)
        reset = datetime.combine(now.date() + timedelta(days=1), time(), tzinfo=UTC)
        raise ProviderBudgetExhaustedError(
            f"Today's AI budget of {self._daily:,} tokens is spent. New AI work is paused until "
            "00:00 UTC; anything already queued runs then.",
            retry_after_seconds=max(1, math.ceil((reset - now).total_seconds())),
        )

    def _today(self) -> date:
        return self._clock.now().astimezone(UTC).date()
