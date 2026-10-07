"""In-process domain-event dispatch (ADR-0103 §3)."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

import pytest

from smb_requirement_agent.application.events import InProcessEventDispatcher
from smb_requirement_agent.infrastructure.persistence.in_memory_transaction import (
    InMemoryTransactionManager,
)
from smb_requirement_agent.requirements.domain.requirement.events import RequirementRevised
from smb_requirement_agent.requirements.infrastructure.in_memory_requirement_repository import (
    InMemoryRequirementRepository,
)
from smb_requirement_agent.shared_kernel.events import DomainEvent
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.characterisation import samples

REQUIREMENT = RequirementId("req-events-1")


@dataclass(frozen=True, kw_only=True)
class _Other(DomainEvent):
    pass


def _dispatcher() -> tuple[InProcessEventDispatcher, InMemoryTransactionManager]:
    transactions = InMemoryTransactionManager(lambda requirement_id: None, RLock())
    return InProcessEventDispatcher(transactions), transactions


def test_handlers_run_in_subscription_order() -> None:
    events, transactions = _dispatcher()
    calls: list[str] = []
    events.subscribe(RequirementRevised, lambda event: calls.append("first"))
    events.subscribe(RequirementRevised, lambda event: calls.append("second"))
    events.subscribe(RequirementRevised, lambda event: calls.append("third"))

    with transactions.transaction():
        events.publish(RequirementRevised(requirement_id=REQUIREMENT))

    assert calls == ["first", "second", "third"]


def test_only_the_exact_event_type_is_dispatched() -> None:
    events, transactions = _dispatcher()
    calls: list[DomainEvent] = []
    events.subscribe(RequirementRevised, calls.append)

    with transactions.transaction():
        events.publish(_Other(requirement_id=REQUIREMENT))
        events.publish(DomainEvent(requirement_id=REQUIREMENT))

    assert calls == []


def test_an_event_without_subscribers_is_a_no_op() -> None:
    events, transactions = _dispatcher()

    with transactions.transaction():
        events.publish(RequirementRevised(requirement_id=REQUIREMENT))


def test_publishing_outside_a_unit_of_work_is_refused() -> None:
    events, _ = _dispatcher()
    calls: list[DomainEvent] = []
    events.subscribe(RequirementRevised, calls.append)

    with pytest.raises(RuntimeError, match="outside a unit of work"):
        events.publish(RequirementRevised(requirement_id=REQUIREMENT))

    assert calls == []


def test_publishing_during_an_external_call_is_refused() -> None:
    events, transactions = _dispatcher()
    events.subscribe(RequirementRevised, lambda event: None)

    with transactions.transaction(), transactions.external_call():
        with pytest.raises(RuntimeError, match="outside a unit of work"):
            events.publish(RequirementRevised(requirement_id=REQUIREMENT))


def test_a_failing_handler_rolls_back_the_whole_unit_of_work() -> None:
    events, transactions = _dispatcher()
    requirements = InMemoryRequirementRepository()
    transactions.enroll(requirements)

    def write(event: RequirementRevised) -> None:
        requirements.add(samples.requirement())

    def fail(event: RequirementRevised) -> None:
        raise ValueError("handler failed")

    events.subscribe(RequirementRevised, write)
    events.subscribe(RequirementRevised, fail)

    with pytest.raises(ValueError, match="handler failed"), transactions.transaction():
        events.publish(RequirementRevised(requirement_id=REQUIREMENT))

    assert requirements.get(samples.REQUIREMENT_ID) is None
