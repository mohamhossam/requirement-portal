"""Provider call counts and token spend held in this process (offline and tests)."""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta


class InMemoryProviderCallLog:
    """One process's count: behind several replicas each would count separately."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: dict[str, dict[str, datetime]] = {}

    def record_unless_full(
        self, actor_key: str, call_id: str, now: datetime, window: timedelta, limit: int
    ) -> datetime | None:
        with self._lock:
            # Calls a full window old stop counting, for every actor, so idle ones are forgotten.
            for key in list(self._calls):
                current = {call: at for call, at in self._calls[key].items() if now - at < window}
                if current:
                    self._calls[key] = current
                else:
                    del self._calls[key]
            calls = self._calls.setdefault(actor_key, {})
            if len(calls) >= limit:
                return min(calls.values())
            calls[call_id] = now
            return None

    def remove(self, actor_key: str, call_id: str) -> None:
        with self._lock:
            calls = self._calls.get(actor_key)
            if calls is not None:
                calls.pop(call_id, None)


class InMemoryProviderSpend:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._days: dict[date, int] = {}

    def add(self, day: date, tokens: int) -> None:
        with self._lock:
            self._days[day] = self._days.get(day, 0) + tokens

    def spent(self, day: date) -> int:
        with self._lock:
            return self._days.get(day, 0)
