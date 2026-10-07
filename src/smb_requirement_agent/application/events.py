"""In-process domain-event dispatch (ADR-0103 §3).

Handlers run synchronously, in the order they were subscribed, inside the publisher's unit of
work and under the Requirement lock it already holds (ADR-0070). A handler that raises
propagates, so the whole unit of work rolls back. Nothing is queued or persisted.

Handlers are subscribed only in the composition root, `interfaces/api/composition/events.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.shared_kernel.events import DomainEvent

E = TypeVar("E", bound=DomainEvent)


class InProcessEventDispatcher:
    """`DomainEventPublisher` that calls each subscribed handler immediately."""

    def __init__(self, transactions: TransactionManagerPort) -> None:
        self._transactions = transactions
        self._handlers: dict[type[DomainEvent], list[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: type[E], handler: Callable[[E], None]) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: DomainEvent) -> None:
        if not self._transactions.in_unit_of_work():
            raise RuntimeError(
                f"{type(event).__name__} was published outside a unit of work. Domain events "
                "are published inside transaction(), never during an external call."
            )
        for handler in self._handlers.get(type(event), ()):
            handler(event)
