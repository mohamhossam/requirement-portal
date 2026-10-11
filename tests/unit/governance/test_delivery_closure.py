"""What a closed Epic delivered, sent to the knowledge service (ontology plan Phase 7).

The tracker's service hook queues a published Epic closed or removed, once per event; the
worker reads its Features' states, renders the catalogue change the decided product impact
implies for what was delivered, and delivers it, retrying until the service answers.
"""

from __future__ import annotations

import base64
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.analysis.application.use_cases.product_impact import product_impact
from smb_requirement_agent.analysis.domain.product_impact import (
    ImpactGap,
    ImpactSystem,
    ProductImpact,
    ProductImpactDecision,
    ProductVerdict,
)
from smb_requirement_agent.application.errors import (
    ServiceResponseError,
    ServiceUnavailableError,
)
from smb_requirement_agent.governance.application.errors import PublicationTargetError
from smb_requirement_agent.governance.application.exports import (
    ExportArchitecture,
    ExportFeature,
    ExportSystem,
    NeutralBacklogExport,
)
from smb_requirement_agent.governance.application.use_cases.delivery_closure import (
    MAX_ATTEMPTS,
    DeliverClosures,
    RecordTrackerEvent,
    TrackerEvent,
    delivery_body,
    epic_outcome,
)
from smb_requirement_agent.governance.application.use_cases.export_breakdown import (
    approved_backlog_document,
)
from smb_requirement_agent.governance.domain.publication.entities import BacklogPublication
from smb_requirement_agent.governance.domain.revision.entities import RevisionNumber
from smb_requirement_agent.governance.infrastructure.publication.fake import FakeBacklogPublisher
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.config.options import AdoPublisher, LLMProvider
from smb_requirement_agent.infrastructure.config.settings import (
    AdoPublicationSettings,
    Settings,
)
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.references.application.ports.delivery_closure import (
    DeliveryClosure,
    DeliveryReceipt,
    EpicOutcome,
)
from smb_requirement_agent.references.application.ports.knowledge_handoff import HandoffStatus
from smb_requirement_agent.references.infrastructure.delivery_closures import (
    InMemoryDeliveryClosures,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.knowledge_doubles import PublishedLibrary, service_for
from tests.unit.analysis.test_product_impact import ANSWER, StubAssessment
from tests.unit.test_knowledge_http_contract import SCHEMAS, _violations
from tests.unit.workflow_helpers import approve_fake_breakdown

SECRET = "s" * 24
HOOK = "/integrations/azure-devops/work-items"
AT = datetime(2026, 10, 20, 15, 30, tzinfo=UTC)
# The catalogue covers nothing yet: the static IP is a capability to realise.
UNCOVERED = replace(ANSWER, coverage=tuple(replace(c, covered=False) for c in ANSWER.coverage))

Answer = DeliveryReceipt | Exception


class RecordingInbox:
    """The knowledge service's deliveries route: answers in turn, then a new change."""

    def __init__(self, *answers: Answer) -> None:
        self.answers = list(answers)
        self.sent: list[dict[str, Any]] = []

    def deliver(self, body: dict[str, Any]) -> DeliveryReceipt:
        self.sent.append(body)
        answer = self.answers.pop(0) if self.answers else DeliveryReceipt("CR-1")
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
    inbox: RecordingInbox

    @property
    def publisher(self) -> FakeBacklogPublisher:
        publisher = self.container.backlog_publisher
        assert isinstance(publisher, FakeBacklogPublisher)
        return publisher

    def worker(self, clock: Clock | None = None) -> DeliverClosures:
        return DeliverClosures(
            self.container.delivery_closures,
            self.container.publication_records,
            self.container.breakdown_repository,
            self.container.backlog_publisher,
            self.inbox,
            clock or Clock(datetime.now(UTC) + timedelta(seconds=5)),
        )


def _portal(secret: str | None) -> Iterator[Portal]:
    inbox = RecordingInbox()
    container = build_container(
        Settings(
            llm_provider=LLMProvider.FAKE,
            ado_publication=AdoPublicationSettings(publisher=AdoPublisher.FAKE, hook_secret=secret),
        ),
        knowledge_service=replace(
            service_for(PublishedLibrary()),
            assessment=StubAssessment(UNCOVERED),
            deliveries=inbox,
        ),
    )
    # The API runs every other worker, but not the delivery worker: each test drives its own.
    workers = {
        name: worker
        for name, worker in container.background_workers.items()
        if name != "delivery_worker"
    }
    with TestClient(create_app(lambda: replace(container, background_workers=workers))) as client:
        yield Portal(client, container, inbox)
    container.close_resources()


@pytest.fixture
def portal() -> Iterator[Portal]:
    yield from _portal(SECRET)


@pytest.fixture
def unhooked() -> Iterator[Portal]:
    yield from _portal(None)


@dataclass(frozen=True)
class Published:
    requirement_id: str
    record: BacklogPublication
    document: NeutralBacklogExport

    def external(self, local_key: str) -> str:
        mapping = self.record.mapping_for(local_key)
        assert mapping is not None
        return mapping.external_id

    @property
    def epic(self) -> str:
        return self.external(self.document.epic.id)

    @property
    def features(self) -> list[str]:
        return [self.external(feature.id) for feature in self.document.epic.features]


def _published(portal: Portal) -> Published:
    requirement_id, _, revision = approve_fake_breakdown(portal.client)
    path = f"/requirements/{requirement_id}/revisions/{revision}/publication"
    preview = portal.client.get(path).json()
    response = portal.client.post(
        path, json={"approval_fingerprint": preview["approval_fingerprint"]}
    )
    assert response.status_code == 200, response.text
    requirement = RequirementId(requirement_id)
    record = portal.container.publication_records.get(requirement)
    stored = portal.container.breakdown_repository.get_breakdown_revision(
        requirement, RevisionNumber(revision)
    )
    assert record is not None and stored is not None
    document = approved_backlog_document(stored)
    assert document is not None
    return Published(requirement_id, record, document)


def _event(work_item: str, state: str | None, event_id: str = "evt-1") -> dict[str, Any]:
    fields = {"System.State": {"oldValue": "Active", "newValue": state}} if state else {}
    return {
        "id": event_id,
        "eventType": "workitem.updated",
        "createdDate": "2026-10-20T15:30:00Z",
        "resource": {"id": 9, "workItemId": int(work_item), "fields": fields},
    }


def _signed(secret: str = SECRET) -> dict[str, str]:
    return {"Authorization": "Basic " + base64.b64encode(f"ado:{secret}".encode()).decode()}


def _hook(portal: Portal, body: dict[str, Any], **headers: str) -> dict[str, Any]:
    response = portal.client.post(HOOK, json=body, headers=headers or _signed())
    assert response.status_code == 202, response.text
    return dict(response.json())


def _queued(portal: Portal) -> list[DeliveryClosure]:
    claimed = []
    later = datetime.now(UTC) + timedelta(seconds=5)
    while item := portal.container.delivery_closures.claim(later, timedelta(minutes=5), "t"):
        claimed.append(item)
    return claimed


def _in_contract(body: dict[str, Any]) -> None:
    assert "DeliveryRequest" in SCHEMAS
    assert _violations(body, {"$ref": "#/components/schemas/DeliveryRequest"}) == []


# The hook ----------------------------------------------------------------------------------


def test_a_closed_published_epic_is_queued_once_per_event(portal: Portal) -> None:
    published = _published(portal)

    answer = _hook(portal, _event(published.epic, "Closed"))
    again = _hook(portal, _event(published.epic, "Closed"))
    later = _hook(portal, _event(published.epic, "Done", "evt-2"))

    closure_id = f"{published.requirement_id}:{published.epic}:evt-1"
    assert answer == again == {"status": "queued", "closure_id": closure_id}
    assert later["closure_id"] == f"{published.requirement_id}:{published.epic}:evt-2"
    first, second = _queued(portal)
    assert (first.closure_id, first.outcome, first.occurred_at) == (
        closure_id,
        EpicOutcome.CLOSED,
        AT,
    )
    assert second.outcome is EpicOutcome.CLOSED


@pytest.mark.parametrize(
    "event",
    [
        lambda epic, feature: _event(epic, "Active"),
        lambda epic, feature: _event(epic, None),
        lambda epic, feature: _event(feature, "Closed"),
        lambda epic, feature: _event("999999", "Closed"),
        lambda epic, feature: {**_event(epic, "Closed"), "eventType": "workitem.commented"},
    ],
    ids=["another state", "no state change", "a feature", "not published", "another event"],
)
def test_every_other_event_is_answered_and_ignored(portal: Portal, event: Any) -> None:
    published = _published(portal)

    answer = _hook(portal, event(published.epic, published.features[0]))

    assert answer == {"status": "ignored", "closure_id": None}
    assert _queued(portal) == []


def test_the_hook_needs_its_secret(portal: Portal) -> None:
    published = _published(portal)
    body = _event(published.epic, "Closed")

    for headers in ({}, _signed("w" * 24), {"Authorization": "Bearer " + SECRET}):
        response = portal.client.post(HOOK, json=body, headers=headers)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"].startswith("Basic")
    assert _queued(portal) == []


def test_without_a_secret_the_hook_is_not_there(unhooked: Portal) -> None:
    response = unhooked.client.post(HOOK, json=_event("1", "Closed"), headers=_signed())

    assert response.status_code == 404
    assert "delivery_worker" in unhooked.container.background_workers


@pytest.mark.parametrize(
    ("state", "outcome"),
    [
        ("Closed", EpicOutcome.CLOSED),
        (" done ", EpicOutcome.CLOSED),
        ("Removed", EpicOutcome.REMOVED),
        ("Resolved", None),
        ("New", None),
    ],
)
def test_which_states_close_or_remove_an_epic(state: str, outcome: EpicOutcome | None) -> None:
    assert epic_outcome(state) is outcome


# The worker against the portal ------------------------------------------------------------


def test_a_closure_is_sent_with_what_was_delivered_and_predicted(portal: Portal) -> None:
    published = _published(portal)
    delivered, open_feature = published.features
    portal.publisher.set_state(delivered, "Closed")
    _hook(portal, _event(published.epic, "Closed"))
    analysis = portal.client.get(f"/requirements/{published.requirement_id}/analysis").json()

    assert portal.worker().deliver_next() is True

    (body,) = portal.inbox.sent
    _in_contract(body)
    assert body["delivery_id"] == f"{published.requirement_id}:{published.epic}:evt-1"
    assert body["state"] == "closed"
    assert body["epic"]["external_id"] == published.epic
    assert body["epic"]["url"] == f"https://work-items.example.invalid/{published.epic}"
    assert body["impact_version"] == f"{analysis['analysis_id']}@{analysis['version']}"
    assert (body["decision"], body["verdict"], body["offering_id"]) == (
        "accepted",
        "change_existing_offering",
        "offering:fiber",
    )
    assert body["predicted_systems"] == [
        {"id": "bcrm", "name": "BCRM", "role": "primary", "change_type": "modify"}
    ]
    assert [
        (item["external_id"], item["state"], item["delivered"]) for item in body["features"]
    ] == [
        (delivered, "Closed", True),
        (open_feature, "New", False),
    ]
    closure = portal.container.delivery_closures.get(body["delivery_id"])
    assert closure is not None
    assert (closure.status, closure.change_request_id, closure.payload) == (
        HandoffStatus.DELIVERED,
        "CR-1",
        body,
    )
    assert portal.worker().deliver_next() is False


def test_a_closure_with_no_feature_done_is_skipped(portal: Portal) -> None:
    published = _published(portal)
    _hook(portal, _event(published.epic, "Closed"))

    assert portal.worker().deliver_next() is True

    assert portal.inbox.sent == []
    closure = portal.container.delivery_closures.get(
        f"{published.requirement_id}:{published.epic}:evt-1"
    )
    assert closure is not None
    assert (closure.status, closure.last_error) == (
        HandoffStatus.SKIPPED,
        "No Feature of the Epic was closed as done.",
    )


def test_a_removed_epic_is_sent_so_a_waiting_closure_is_withdrawn(portal: Portal) -> None:
    published = _published(portal)
    _hook(portal, _event(published.epic, "Removed"))
    portal.inbox.answers.append(DeliveryReceipt(None, ("CR-1",)))

    assert portal.worker().deliver_next() is True

    (body,) = portal.inbox.sent
    _in_contract(body)
    assert body["state"] == "removed"
    assert "features" not in body and "changes" not in body
    closure = portal.container.delivery_closures.get(body["delivery_id"])
    assert closure is not None
    assert (closure.status, closure.change_request_id) == (HandoffStatus.DELIVERED, None)


def test_a_closure_is_rendered_once_and_every_retry_sends_the_same_body(
    portal: Portal,
) -> None:
    published = _published(portal)
    first, second = published.features
    portal.publisher.set_state(first, "Closed")
    _hook(portal, _event(published.epic, "Closed"))
    portal.inbox.answers.append(ServiceUnavailableError("down"))
    clock = Clock(datetime.now(UTC) + timedelta(seconds=5))
    worker = portal.worker(clock)

    assert worker.deliver_next() is True
    portal.publisher.set_state(second, "Closed")
    clock.at += timedelta(minutes=1)
    assert worker.deliver_next() is True

    sent, again = portal.inbox.sent
    assert sent == again
    assert [item["delivered"] for item in again["features"]] == [True, False]


# The catalogue changes --------------------------------------------------------------------


def _system(identifier: str, name: str, *, catalogued: bool = True) -> ExportSystem:
    return ExportSystem(identifier, name, catalogued, (), (), (), ())


def _mapped(feature: ExportFeature, *systems: ExportSystem) -> ExportFeature:
    architecture = ExportArchitecture("rel-2026-10", AT, systems, ())
    return replace(feature, architecture=architecture, stories=())


def _closure() -> DeliveryClosure:
    return DeliveryClosure(
        closure_id="REQ-1:4711:evt-1",
        requirement_id="REQ-1",
        epic_external_id="4711",
        outcome=EpicOutcome.CLOSED,
        occurred_at=AT,
        created_at=AT,
        next_attempt_at=AT,
    )


def _impact(verdict: ProductVerdict | None = None) -> ProductImpact:
    suggested = product_impact(UNCOVERED, AT)
    if verdict is None:
        return suggested.decide(ProductImpactDecision.ACCEPTED, FAKE_ACTORS[0], AT)
    return suggested.decide(
        ProductImpactDecision.OVERRIDDEN,
        FAKE_ACTORS[0],
        AT,
        verdict=verdict,
        rationale="A new offering.",
    )


@pytest.fixture
def published(portal: Portal) -> Published:
    return _published(portal)


def _body(
    published: Published,
    systems: tuple[tuple[ExportSystem, ...], tuple[ExportSystem, ...]],
    states: tuple[str, str] = ("Closed", "Closed"),
    impact: ProductImpact | None = None,
) -> dict[str, Any]:
    epic = published.document.epic
    features = tuple(
        _mapped(feature, *mapped) for feature, mapped in zip(epic.features, systems, strict=True)
    )
    document = replace(published.document, epic=replace(epic, features=features))
    body = delivery_body(
        _closure(),
        published.record,
        document,
        impact or _impact(),
        "ANA-1@7",
        dict(zip(published.features, states, strict=True)),
    )
    _in_contract(body)
    return body


def test_a_delivered_system_on_the_path_realises_the_needed_concept(
    published: Published,
) -> None:
    body = _body(published, ((_system("BCRM", "BCRM"),), (_system("cim", "CIM"),)))

    first, second = published.document.epic.features
    # The weak usage quota is a guess, so it is left out.
    assert body["changes"] == [
        {
            "op": "realise_concept",
            "concept_id": "cap:static-ip",
            "concept_label": "Static IP",
            "system_id": "bcrm",
            "system_name": "BCRM",
            "feature_ids": [first.id],
        },
        {
            "op": "offer_concept",
            "concept_id": "cap:static-ip",
            "concept_label": "Static IP",
            "offering_id": "offering:fiber",
            "offering_name": body["offering_name"],
            "feature_ids": [first.id],
        },
    ]
    assert [item["systems"] for item in body["features"]] == [
        [{"id": "BCRM", "name": "BCRM"}],
        [{"id": "cim", "name": "CIM"}],
    ]
    assert second.id not in body["changes"][0]["feature_ids"]


def test_a_covered_need_changes_nothing(published: Published) -> None:
    impact = _impact()
    covered = replace(impact, needs=tuple(replace(n, covered=True) for n in impact.needs))

    body = _body(published, ((_system("bcrm", "BCRM"),), ()), impact=covered)

    assert body["changes"] == []


def test_a_gap_on_a_delivered_system_ties_it_when_no_path_does(published: Published) -> None:
    impact = _impact()
    pathless = replace(
        impact,
        systems=(ImpactSystem("cim", "CIM", "supporting", "configure"),),
        gaps=(ImpactGap("capability", "cap:static-ip", "Static IP", "Nowhere yet.", "cim"),),
    )

    body = _body(published, ((), (_system("cim", "CIM"),)), impact=pathless)

    assert [(item["op"], item.get("system_id")) for item in body["changes"]] == [
        ("realise_concept", "cim"),
        ("offer_concept", None),
    ]


def test_with_nothing_tied_the_offering_is_asked_only_when_all_was_delivered(
    published: Published,
) -> None:
    systems = ((_system("cim", "CIM"),), ())

    whole = _body(published, systems)
    partial = _body(published, systems, states=("Closed", "Removed"))

    first, second = published.document.epic.features
    assert [(item["op"], item["feature_ids"]) for item in whole["changes"]] == [
        ("offer_concept", [first.id, second.id])
    ]
    assert partial["changes"] == []
    assert [item["delivered"] for item in partial["features"]] == [True, False]


@pytest.mark.parametrize(
    "verdict", [ProductVerdict.NEW_OFFERING_IN_FAMILY, ProductVerdict.NEW_PRODUCT_LINE]
)
def test_a_new_offering_is_not_asked_about(published: Published, verdict: ProductVerdict) -> None:
    impact = _impact(verdict=verdict)

    body = _body(published, ((_system("bcrm", "BCRM"),), ()), impact=impact)

    assert [item["op"] for item in body["changes"]] == ["realise_concept"]


def test_a_system_the_catalogue_lacks_is_sent_by_name(published: Published) -> None:
    body = _body(
        published, ((_system("tmp-1", "New portal", catalogued=False),), (_system("cim", "CIM"),))
    )

    assert body["features"][0]["systems"] == [{"id": None, "name": "New portal"}]


# The worker alone --------------------------------------------------------------------------


class Publications:
    def __init__(self, record: BacklogPublication | None) -> None:
        self.record = record

    def get(self, _requirement_id: RequirementId) -> BacklogPublication | None:
        return self.record

    def find_by_work_item(self, kind: str, external_id: str) -> BacklogPublication | None:
        return self.record if (kind, external_id) == ("epic", "4711") else None

    def save(self, publication: BacklogPublication) -> None:
        self.record = publication


class Tracker(FakeBacklogPublisher):
    def __init__(self, *failures: Exception) -> None:
        super().__init__()
        self.failures = list(failures)

    def states(self, external_ids: tuple[str, ...]) -> dict[str, str]:
        if self.failures:
            raise self.failures.pop(0)
        return dict.fromkeys(external_ids, "Closed")


def _rendered(**changes: Any) -> DeliveryClosure:
    return replace(_closure(), payload={"delivery_id": "REQ-1:4711:evt-1"}, **changes)


def _alone(
    inbox: RecordingInbox, closure: DeliveryClosure, clock: Clock | None = None
) -> tuple[InMemoryDeliveryClosures, DeliverClosures]:
    outbox = InMemoryDeliveryClosures(RLock())
    outbox.enqueue(closure)
    worker = DeliverClosures(
        outbox,
        Publications(None),
        None,  # type: ignore[arg-type]
        Tracker(),
        inbox,
        clock or Clock(AT),
    )
    return outbox, worker


def test_the_hook_queues_each_event_once() -> None:
    outbox = InMemoryDeliveryClosures(RLock())
    record = BacklogPublication(RequirementId("REQ-1"), "fake")
    use_case = RecordTrackerEvent(Publications(record), outbox, Clock(AT))
    event = TrackerEvent("evt-1", "4711", "Closed", AT)

    first = use_case.execute(event)
    second = use_case.execute(event)

    assert first is not None and second is not None
    assert first.closure_id == second.closure_id == "REQ-1:4711:evt-1"
    assert outbox.enqueue(first) is False
    assert use_case.execute(replace(event, work_item_id="4712")) is None


def test_an_unreachable_service_is_retried_with_a_growing_pause() -> None:
    inbox = RecordingInbox(
        ServiceUnavailableError("down"), ServiceResponseError(503, "busy"), DeliveryReceipt("CR-9")
    )
    clock = Clock(AT)
    outbox, worker = _alone(inbox, _rendered(), clock)

    assert worker.deliver_next() is True
    assert worker.deliver_next() is False
    clock.at += timedelta(minutes=1)
    assert worker.deliver_next() is True
    clock.at += timedelta(minutes=2)
    assert worker.deliver_next() is True

    closure = outbox.get("REQ-1:4711:evt-1")
    assert closure is not None
    assert (closure.status, closure.attempts, closure.change_request_id) == (
        HandoffStatus.DELIVERED,
        3,
        "CR-9",
    )


@pytest.mark.parametrize("status", [400, 409, 413, 422])
def test_a_closure_the_service_refuses_is_not_sent_again(status: int) -> None:
    inbox = RecordingInbox(ServiceResponseError(status, "refused"))
    outbox, worker = _alone(inbox, _rendered())

    assert worker.deliver_next() is True
    assert worker.deliver_next() is False

    closure = outbox.get("REQ-1:4711:evt-1")
    assert closure is not None
    assert (closure.status, closure.last_error) == (
        HandoffStatus.FAILED,
        f"The knowledge service refused it ({status}).",
    )


def test_a_closure_is_given_up_after_its_last_attempt() -> None:
    inbox = RecordingInbox(ServiceUnavailableError("down"))
    outbox, worker = _alone(inbox, _rendered(attempts=MAX_ATTEMPTS - 1))

    worker.deliver_next()

    closure = outbox.get("REQ-1:4711:evt-1")
    assert closure is not None
    assert (closure.status, closure.attempts) == (HandoffStatus.FAILED, MAX_ATTEMPTS)


def test_a_closure_for_a_requirement_no_longer_published_is_skipped() -> None:
    inbox = RecordingInbox()
    outbox, worker = _alone(inbox, _closure())

    worker.deliver_next()

    closure = outbox.get("REQ-1:4711:evt-1")
    assert closure is not None
    assert (closure.status, closure.last_error) == (
        HandoffStatus.SKIPPED,
        "The Requirement has no published revision.",
    )
    assert inbox.sent == []


def test_a_tracker_that_does_not_answer_is_retried(portal: Portal) -> None:
    published = _published(portal)
    _hook(portal, _event(published.epic, "Closed"))
    clock = Clock(datetime.now(UTC) + timedelta(seconds=5))
    worker = DeliverClosures(
        portal.container.delivery_closures,
        portal.container.publication_records,
        portal.container.breakdown_repository,
        Tracker(PublicationTargetError("Azure DevOps could not be reached (ConnectError).")),
        portal.inbox,
        clock,
    )

    assert worker.deliver_next() is True
    closure = portal.container.delivery_closures.get(
        f"{published.requirement_id}:{published.epic}:evt-1"
    )
    assert closure is not None
    assert closure.status is HandoffStatus.PENDING
    assert closure.payload is None
    assert closure.last_error == (
        "The work-item tracker did not answer: Azure DevOps could not be reached (ConnectError)."
    )
    clock.at += timedelta(minutes=1)
    assert worker.deliver_next() is True

    (body,) = portal.inbox.sent
    assert all(item["delivered"] for item in body["features"])
