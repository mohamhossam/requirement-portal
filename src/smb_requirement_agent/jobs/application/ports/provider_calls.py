"""Where provider-calling operations are counted, so every process shares one count."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Protocol


class ProviderCallLogPort(Protocol):
    """Each actor's provider-calling operations within the last window (ADR-0106)."""

    def record_unless_full(
        self, actor_key: str, call_id: str, now: datetime, window: timedelta, limit: int
    ) -> datetime | None:
        """Record the call unless `limit` calls already fall within the window.

        Returns None when recorded, or the oldest counted call's time when full,
        so the caller can say when the next call will be accepted.
        """
        ...

    def remove(self, actor_key: str, call_id: str) -> None:
        """Forget a recorded call; forgetting one twice, or one never recorded, is harmless."""
        ...


class ProviderSpendPort(Protocol):
    """Tokens the model providers reported spending, per UTC day (ADR-0106)."""

    def add(self, day: date, tokens: int) -> None: ...

    def spent(self, day: date) -> int: ...
