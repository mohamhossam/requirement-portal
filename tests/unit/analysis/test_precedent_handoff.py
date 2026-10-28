"""Decided product verdicts sent to the knowledge service as precedents (ontology Phase 5)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.analysis.application.use_cases.precedent_handoff import (
    MAX_ATTEMPTS,
    MAX_NEED,
    MAX_NEEDS,
    DeliverPrecedents,
)
from smb_requirement_agent.application.errors import (
    PersistenceError,
    ServiceResponseError,
    ServiceUnavailableError,
)
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.references.application.ports.architecture_assessment import (
    AssessedFacet,
)
from smb_requirement_agent.references.application.ports.knowledge_handoff import HandoffStatus
from smb_requirement_agent.references.application.ports.precedent_handoff import (
    PrecedentHandoff,
)
from smb_requirement_agent.references.infrastructure.knowledge_client import HttpPrecedentInbox
from smb_requirement_agent.references.infrastructure.precedent_handoffs import (
    InMemoryPrecedentHandoffs,
)
from tests.knowledge_doubles import PublishedLibrary, service_for
from tests.unit.analysis.test_product_impact import (
    ANSWER,
    StubAssessment,
    _decide,
    _requirement,
)
from tests.unit.test_knowledge_http_contract import _assert_in_contract, _client
from tests.unit.workflow_helpers import post_analysis

AT = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
RECEIPT = {"precedent_id": "ANA-1", "recorded": True, "dropped_systems": []}

Answer = bool | Exception


class RecordingInbox:
    """The knowledge service's precedents route: answers in turn, then True."""

    def __init__(self, *answers: Answer) -> None:
        self.answers = list(answers)
        self.sent: list[dict[str, Any]] = []

    def record(self, precedent: dict[str, Any]) -> bool:
        self.sent.append(precedent)
        answer = self.answers.pop(0) if self.answers else True
        if isinstance(answer, Exception):
            raise answer
        return answer


class Clock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


@dataclass(frozen=True)
class Portal:
    client: TestClient
    container: Container
    assessment: StubAssessment


def _portal(inbox: RecordingInbox | None) -> Iterator[Portal]:
    assessment = StubAssessment()
    container = build_container(
        Settings(llm_provider=LLMProvider.FAKE),
        knowledge_service=replace(
            service_for(PublishedLibrary()), assessment=assessment, precedents=inbox
        ),
    )
    # The API runs every other worker, but not the precedent worker: each test drives its own.
    workers = {
        name: worker
        for name, worker in container.background_workers.items()
        if name != "precedent_worker"
    }
    application = create_app(lambda: replace(container, background_workers=workers))
    with TestClient(application) as client:
        yield Portal(client, container, assessment)
    container.close_resources()


@pytest.fixture
def portal() -> Iterator[Portal]:
    yield from _portal(RecordingInbox())


@pytest.fixture
def offline() -> Iterator[Portal]:
    yield from _portal(None)


def _decided(portal: Portal, **decision: object) -> tuple[str, dict[str, Any]]:
    requirement_id = _requirement(portal.client)
    assert post_analysis(portal.client, requirement_id).succeeded
    return requirement_id, _decide(portal.client, requirement_id, **decision)


def _queued(portal: Portal) -> list[PrecedentHandoff]:
    """Every handoff due, claimed in order."""
    claimed = []
    later = datetime.now(UTC) + timedelta(seconds=5)
    while item := portal.container.precedent_handoffs.claim(later, timedelta(minutes=5), "t"):
        claimed.append(item)
    return claimed


def _sent_as_the_contract_describes(precedent: dict[str, Any]) -> None:
    seen: list[httpx.Request] = []
    inbox = HttpPrecedentInbox(_client(lambda _r: httpx.Response(201, json=RECEIPT), seen))
    assert inbox.record(precedent) is True
    (request,) = seen
    _assert_in_contract(request)


# Deciding queues a precedent ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("decision", "verdict"),
    [
        ({"decision": "accepted"}, "change_existing_offering"),
        (
            {"decision": "overridden", "verdict": "new_plan", "rationale": "A separate plan."},
            "new_plan",
        ),
        ({"decision": "unknown"}, None),
    ],
)
def test_each_decision_queues_one_precedent_the_contract_allows(
    portal: Portal, decision: dict[str, object], verdict: str | None
) -> None:
    requirement_id, analysis = _decided(portal, **decision)

    (handoff,) = _queued(portal)

    payload = handoff.payload
    _sent_as_the_contract_describes(payload)
    assert handoff.requirement_id == requirement_id
    # One precedent per analysis; each decision on it is a later version.
    assert payload["version"] == f"{payload['precedent_id']}@{analysis['version']}"
    assert handoff.handoff_id == payload["version"]
    assert payload["release_id"] == "rel-2026-10"
    assert payload["decision"] == decision["decision"]
    assert payload["suggested_verdict"] == "change_existing_offering"
    assert payload["verdict"] == verdict
    assert payload["offering_id"] == "offering:fiber"
    # The weak link to a usage quota is a guess, so it is not sent as a need.
    assert payload["concept_ids"] == ["cap:static-ip"]
    assert payload["systems"] == [{"id": "bcrm", "role": "primary", "change_type": "modify"}]
    assert "Static IP quota" in payload["text"][0]
    # The needs it was assessed with, which precedents are compared by.
    assert payload["needs"] == ["Static IP for SMB fibre"]


def test_the_needs_sent_keep_to_the_contract_limits(portal: Portal) -> None:
    long_need = "Static IP " + "x" * 1_500
    portal.assessment.answer = replace(
        ANSWER,
        facets=(
            AssessedFacet("need", long_need, "static IP"),
            *(AssessedFacet("need", f"Need {index}", "static IP") for index in range(30)),
        ),
    )
    _decided(portal, decision="accepted")

    (handoff,) = _queued(portal)

    needs = handoff.payload["needs"]
    _sent_as_the_contract_describes(handoff.payload)
    assert len(needs) == MAX_NEEDS == 24
    assert needs[0] == long_need[:MAX_NEED] and len(needs[0]) == 1_000
    assert needs[1:3] == ["Need 0", "Need 1"]


def test_the_assessment_names_the_requirement_so_its_own_precedent_is_left_out(
    portal: Portal,
) -> None:
    requirement_id, _ = _decided(portal, decision="accepted")

    assert portal.assessment.queries[-1].requirement_id == requirement_id


def test_deciding_again_queues_the_later_decision_too(portal: Portal) -> None:
    requirement_id, _ = _decided(portal, decision="accepted")
    _decide(portal.client, requirement_id, decision="unknown")

    first, second = _queued(portal)

    assert (first.payload["decision"], second.payload["decision"]) == ("accepted", "unknown")
    assert first.payload["precedent_id"] == second.payload["precedent_id"]
    assert first.handoff_id != second.handoff_id


def test_without_a_knowledge_service_a_decision_queues_nothing(offline: Portal) -> None:
    _decided(offline, decision="accepted")

    assert _queued(offline) == []
    assert "precedent_worker" not in offline.container.background_workers


def test_the_worker_runs_only_with_a_knowledge_service(portal: Portal) -> None:
    assert "precedent_worker" in portal.container.background_workers


def test_the_worker_delivers_what_the_decision_queued(portal: Portal) -> None:
    inbox = RecordingInbox()
    requirement_id, _ = _decided(portal, decision="accepted")
    outcomes: list[str] = []
    worker = DeliverPrecedents(
        portal.container.precedent_handoffs,
        inbox,
        Clock(datetime.now(UTC) + timedelta(seconds=5)),
        record=lambda outcome, _seconds: outcomes.append(outcome),
    )

    assert worker.deliver_next() is True
    assert worker.deliver_next() is False

    (sent,) = inbox.sent
    assert (sent["requirement_id"], sent["decision"]) == (requirement_id, "accepted")
    assert outcomes == ["delivered"]


# Delivering --------------------------------------------------------------------------------


def _handoff(**changes: Any) -> PrecedentHandoff:
    return replace(
        PrecedentHandoff(
            handoff_id="ANA-1@3",
            requirement_id="REQ-1",
            payload={"precedent_id": "ANA-1"},
            created_at=AT,
            next_attempt_at=AT,
        ),
        **changes,
    )


def _alone(
    inbox: RecordingInbox, clock: Clock | None = None, **changes: Any
) -> tuple[InMemoryPrecedentHandoffs, DeliverPrecedents]:
    outbox = InMemoryPrecedentHandoffs(RLock())
    outbox.enqueue(_handoff(**changes))
    return outbox, DeliverPrecedents(outbox, inbox, clock or Clock(AT))


def test_a_delivered_decision_is_not_sent_again() -> None:
    inbox = RecordingInbox(False)
    outbox, worker = _alone(inbox)

    assert worker.deliver_next() is True
    assert worker.deliver_next() is False

    handoff = outbox.get("ANA-1@3")
    assert handoff is not None
    # Already kept there (False) is delivered all the same.
    assert (handoff.status, handoff.delivered_at, handoff.attempts) == (
        HandoffStatus.DELIVERED,
        AT,
        1,
    )
    assert inbox.sent == [{"precedent_id": "ANA-1"}]


def test_an_unreachable_or_absent_service_is_retried_with_a_growing_pause() -> None:
    inbox = RecordingInbox(
        ServiceUnavailableError("down"), ServiceResponseError(404, "not deployed yet"), True
    )
    clock = Clock(AT)
    outbox, worker = _alone(inbox, clock)

    assert worker.deliver_next() is True
    # Not due again for a minute, then two.
    assert worker.deliver_next() is False
    clock.at += timedelta(minutes=1)
    assert worker.deliver_next() is True
    handoff = outbox.get("ANA-1@3")
    assert handoff is not None
    assert handoff.last_error == "The knowledge service answered 404."
    clock.at += timedelta(minutes=1)
    assert worker.deliver_next() is False
    clock.at += timedelta(minutes=1)
    assert worker.deliver_next() is True

    handoff = outbox.get("ANA-1@3")
    assert handoff is not None
    assert (handoff.status, handoff.attempts) == (HandoffStatus.DELIVERED, 3)
    assert inbox.sent == [{"precedent_id": "ANA-1"}] * 3


@pytest.mark.parametrize("status", [400, 409, 413, 422])
def test_a_decision_the_service_refuses_is_not_sent_again(status: int) -> None:
    inbox = RecordingInbox(ServiceResponseError(status, "refused"))
    outbox, worker = _alone(inbox)

    assert worker.deliver_next() is True

    handoff = outbox.get("ANA-1@3")
    assert handoff is not None
    assert (handoff.status, handoff.last_error) == (
        HandoffStatus.FAILED,
        f"The knowledge service refused it ({status}).",
    )
    assert worker.deliver_next() is False


def test_a_decision_is_given_up_after_its_last_attempt() -> None:
    inbox = RecordingInbox(ServiceUnavailableError("down"))
    outbox, worker = _alone(inbox, attempts=MAX_ATTEMPTS - 1)

    assert worker.deliver_next() is True

    handoff = outbox.get("ANA-1@3")
    assert handoff is not None
    assert (handoff.status, handoff.attempts) == (HandoffStatus.FAILED, MAX_ATTEMPTS)
    assert handoff.last_error == (
        f"The knowledge service could not be reached. Gave up after {MAX_ATTEMPTS} attempts."
    )


def test_the_longest_pause_is_an_hour() -> None:
    inbox = RecordingInbox(ServiceUnavailableError("down"))
    outbox, worker = _alone(inbox, attempts=20)

    worker.deliver_next()

    handoff = outbox.get("ANA-1@3")
    assert handoff is not None
    assert handoff.next_attempt_at == AT + timedelta(hours=1)


# The outbox --------------------------------------------------------------------------------


def test_the_outbox_keeps_one_handoff_per_version_and_leases_it_to_one_worker() -> None:
    outbox = InMemoryPrecedentHandoffs(RLock())
    assert outbox.enqueue(_handoff()) is True
    assert outbox.enqueue(_handoff(requirement_id="REQ-2")) is False

    claimed = outbox.claim(AT, timedelta(minutes=5), "first")
    assert claimed is not None
    assert (claimed.lease_token, claimed.attempts, claimed.version) == ("first", 1, 2)
    # Leased: no one else takes it until the lease runs out.
    assert outbox.claim(AT + timedelta(minutes=4), timedelta(minutes=5), "second") is None
    again = outbox.claim(AT + timedelta(minutes=5), timedelta(minutes=5), "second")
    assert again is not None and again.lease_token == "second"
    # The first worker's write is refused: the handoff moved on without it.
    with pytest.raises(PersistenceError):
        outbox.save(claimed.retried("late", AT), claimed.version)


def test_a_rolled_back_decision_leaves_no_handoff() -> None:
    outbox = InMemoryPrecedentHandoffs(RLock())
    before = outbox.snapshot_state()
    outbox.enqueue(_handoff())

    outbox.restore_state(before)

    assert outbox.get("ANA-1@3") is None
