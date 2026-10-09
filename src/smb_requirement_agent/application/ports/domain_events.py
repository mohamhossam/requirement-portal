"""Publishing domain events (ADR-0103 §3)."""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.shared_kernel.events import DomainEvent


class DomainEventPublisher(Protocol):
    """Hands an event to its handlers, synchronously, inside the caller's unit of work."""

    def publish(self, event: DomainEvent) -> None: ...
