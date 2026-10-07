"""Requirement work's local copy of the library's citable state (ADR-0099)."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from threading import RLock

import pytest
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.errors import (
    PersistenceError,
    RequirementAnalysisConflictError,
)
from smb_requirement_agent.application.ports.architecture_knowledge import ActiveRelease
from smb_requirement_agent.application.ports.knowledge_events import (
    ARCHITECTURE_RELEASE_ACTIVATED,
    REFERENCE_DOCUMENT_CHANGED,
    KnowledgeEvent,
)
from smb_requirement_agent.application.use_cases.reference_currency import (
    CurrentArchitectureRelease,
    ProjectKnowledgeEvents,
    ReferenceCurrency,
)
from smb_requirement_agent.domain.document.reference import (
    CurrentPublication,
    ReferenceDocumentState,
)
from smb_requirement_agent.infrastructure.persistence.architecture_release_state import (
    InMemoryArchitectureReleaseState,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_transaction import (
    InMemoryTransactionManager,
)
from smb_requirement_agent.infrastructure.persistence.knowledge_payloads import (
    PayloadKnowledgeStateDecoder,
    reference_document_state_from_payload,
    reference_document_state_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.reference_publications import (
    InMemoryReferencePublications,
)
from smb_requirement_agent.requirements.domain.document.errors import InvalidDocumentError
from smb_requirement_agent.shared_kernel.citation import (
    PublishedReference,
    normalize_search,
)
from tests.conftest import FAKE_PROVIDER_SETTINGS
from tests.knowledge_doubles import container_with_library, sync

NOW = datetime(2026, 10, 2, 9, tzinfo=UTC)
TEXT = "XGPON coverage is required."
PUBLISHED = CurrentPublication(
    "pub-1", "f" * 64, "ver-1", 1, "rev-1", (("b1", "Line 1"),), (("b1", TEXT),)
)
STATE = ReferenceDocumentState("doc-1", "owner", "Eligibility", 4, PUBLISHED)


class _EventFeed:
    """The knowledge service's event feed, as requirement work reads it: oldest first."""

    def __init__(self) -> None:
        self.events: list[KnowledgeEvent] = []

    def append(self, kind: str, subject_id: str, payload: object) -> int:
        seq = len(self.events) + 1
        self.events.append(KnowledgeEvent(seq, kind, subject_id, payload, NOW))
        return seq

    def after(self, seq: int, limit: int) -> tuple[KnowledgeEvent, ...]:
        return tuple(e for e in self.events if e.seq > seq)[:limit]


def _citation(**changes: object) -> PublishedReference:
    citation = PublishedReference(
        "doc-1",
        "Eligibility",
        "ver-1",
        1,
        "rev-1",
        "pub-1",
        "f" * 64,
        "b1",
        "Line 1",
        "XGPON coverage",
        0,
        14,
        hashlib.sha256(normalize_search("XGPON coverage").encode()).hexdigest(),
    )
    return replace(citation, **changes)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {"publication_id": "pub-0"},
        {"approval_fingerprint": "e" * 64},
        {"title": "Renamed"},
        {"version_number": 2},
        {"location": "Line 9"},
        {"block_id": "b9"},
        {"excerpt": "XGPON coverabe", "lineage_hash": hashlib.sha256(b"x").hexdigest()},
        {"lineage_hash": hashlib.sha256(b"tampered").hexdigest()},
    ],
)
def test_a_citation_is_current_only_while_it_quotes_the_live_publication_exactly(
    changes: dict[str, object],
) -> None:
    assert STATE.cites(_citation())
    assert not STATE.cites(_citation(**changes))
    assert not replace(STATE, published=None).cites(_citation())


def test_states_survive_the_event_payload_and_refuse_malformed_ones() -> None:
    assert (
        reference_document_state_from_payload(reference_document_state_to_payload(STATE)) == STATE
    )
    withdrawn = replace(STATE, published=None)
    assert (
        reference_document_state_from_payload(reference_document_state_to_payload(withdrawn))
        == withdrawn
    )
    assert withdrawn.publication_state == "4:withdrawn"
    assert STATE.publication_state == "4:pub-1"
    malformed: tuple[object, ...] = (
        {},
        {"document_id": 1},
        [],
        {**reference_document_state_to_payload(STATE), "published": {"x": 1}},
    )
    for payload in malformed:
        with pytest.raises(InvalidDocumentError):
            reference_document_state_from_payload(payload)


def _currency() -> tuple[
    ReferenceCurrency,
    InMemoryReferencePublications,
    _EventFeed,
    ProjectKnowledgeEvents,
]:
    lock = RLock()
    states = InMemoryReferencePublications(lock)
    events = _EventFeed()
    transactions = InMemoryTransactionManager(lambda _: None, lock)
    transactions.enroll(states)
    projector = ProjectKnowledgeEvents(
        events,
        states,
        InMemoryArchitectureReleaseState(lock),
        transactions,
        FixedClock(NOW),
        decoder=PayloadKnowledgeStateDecoder(),
    )
    return ReferenceCurrency(states, transactions), states, events, projector


def test_the_copy_catches_up_from_the_event_feed_and_checks_citations_locally() -> None:
    currency, states, events, projector = _currency()
    events.append(REFERENCE_DOCUMENT_CHANGED, "doc-1", reference_document_state_to_payload(STATE))
    with pytest.raises(RequirementAnalysisConflictError):
        currency.require_current((_citation(),))

    assert projector.project_next()
    currency.require_current((_citation(),))
    assert not projector.project_next()

    events.append(
        REFERENCE_DOCUMENT_CHANGED,
        "doc-1",
        reference_document_state_to_payload(replace(STATE, published=None)),
    )
    assert projector.project_next()
    with pytest.raises(RequirementAnalysisConflictError, match="withdrawn or replaced"):
        currency.require_current((_citation(),))
    assert states.cursor() == 2


def test_an_older_event_never_replaces_a_newer_state() -> None:
    _, states, _, _ = _currency()
    states.apply(5, STATE)
    states.apply(3, replace(STATE, published=None))
    assert states.get("doc-1") == STATE


class _GappedOutbox:
    """Events 1 and 3 are visible; 2 is still being written (or was rolled back)."""

    def __init__(self, gap_written_at: datetime) -> None:
        payload = reference_document_state_to_payload(STATE)
        self.events = (
            KnowledgeEvent(1, REFERENCE_DOCUMENT_CHANGED, "doc-1", payload, NOW),
            KnowledgeEvent(3, REFERENCE_DOCUMENT_CHANGED, "doc-2", payload, gap_written_at),
        )

    def append(self, kind: str, subject_id: str, payload: object) -> int:
        raise AssertionError("not written in this test")

    def after(self, seq: int, limit: int) -> tuple[KnowledgeEvent, ...]:
        return tuple(e for e in self.events if e.seq > seq)[:limit]


@pytest.mark.parametrize(
    ("written", "cursor"),
    [(NOW - timedelta(seconds=5), 1), (NOW - timedelta(minutes=5), 3)],
)
def test_the_cursor_waits_at_a_fresh_gap_and_steps_over_an_old_one(
    written: datetime, cursor: int
) -> None:
    _, states, _, _ = _currency()
    transactions = InMemoryTransactionManager(lambda _: None, RLock())
    projector = ProjectKnowledgeEvents(
        _GappedOutbox(written),
        states,
        InMemoryArchitectureReleaseState(RLock()),
        transactions,
        FixedClock(NOW),
        decoder=PayloadKnowledgeStateDecoder(),
    )

    projector.project_next()

    # Every visible event is applied either way; only the cursor waits.
    assert states.get("doc-1") is not None
    assert states.cursor() == cursor


def test_the_active_release_follows_activation_events_and_never_goes_back() -> None:
    lock = RLock()
    events = _EventFeed()
    releases = InMemoryArchitectureReleaseState(lock)
    transactions = InMemoryTransactionManager(lambda _: None, lock)
    transactions.enroll(releases)
    projector = ProjectKnowledgeEvents(
        events,
        InMemoryReferencePublications(lock),
        releases,
        transactions,
        FixedClock(NOW),
        decoder=PayloadKnowledgeStateDecoder(),
    )
    current = CurrentArchitectureRelease(releases)
    with pytest.raises(PersistenceError, match="No active architecture release"):
        current.active_release_id()

    events.append(ARCHITECTURE_RELEASE_ACTIVATED, "r1", {"release_id": "r1"})
    events.append(
        ARCHITECTURE_RELEASE_ACTIVATED, "r2", {"release_id": "r2", "name": "Q4 catalogue"}
    )
    projector.drain()
    assert current.active_release_id() == "r2"
    # The knowledge service names the version; an older event without a name still applies.
    assert current.active_release() == ActiveRelease("r2", "Q4 catalogue")
    releases.apply(1, ActiveRelease("r1"))
    assert current.active_release_id() == "r2"

    events.append(ARCHITECTURE_RELEASE_ACTIVATED, "r3", {"release": "malformed"})
    with pytest.raises(PersistenceError, match="malformed"):
        projector.drain()
    assert current.active_release_id() == "r2"


def test_the_containers_copy_follows_the_knowledge_services_feed() -> None:
    """A withdrawal reaches requirement work through the feed, never by reading the library."""
    container, library = container_with_library(FAKE_PROVIDER_SETTINGS)
    (citation,) = library.publish("Eligibility", (TEXT,))
    with pytest.raises(RequirementAnalysisConflictError):
        container.reference_currency.require_current((citation,))
    sync(container)
    container.reference_currency.require_current((citation,))

    library.withdraw(citation.document_id)
    # Until the feed is read, the copy still holds the publication it last saw.
    container.reference_currency.require_current((citation,))
    sync(container)
    with pytest.raises(RequirementAnalysisConflictError, match="withdrawn or replaced"):
        container.reference_currency.require_current((citation,))
    republished = library.publish("Eligibility", (TEXT,), document_id=citation.document_id)
    sync(container)
    container.reference_currency.require_current(republished)
    with pytest.raises(RequirementAnalysisConflictError):
        container.reference_currency.require_current((citation,))


def test_the_review_due_date_travels_with_the_state_and_old_copies_still_read() -> None:
    reviewed = replace(STATE, review_due_on=date(2026, 10, 1))
    assert (
        reference_document_state_from_payload(reference_document_state_to_payload(reviewed))
        == reviewed
    )
    legacy = {
        key: value
        for key, value in reference_document_state_to_payload(STATE).items()
        if key != "review_due_on"
    }
    assert reference_document_state_from_payload(legacy).review_due_on is None
    with pytest.raises(InvalidDocumentError):
        reference_document_state_from_payload(
            {**reference_document_state_to_payload(STATE), "review_due_on": "soon"}
        )
    # Overdue from the due day itself; never before it, and never without a date.
    assert reviewed.review_overdue(date(2026, 10, 1))
    assert not reviewed.review_overdue(date(2026, 9, 30))
    assert not STATE.review_overdue(date(2030, 1, 1))


def test_overdue_reviews_are_worked_out_from_the_copy_when_read() -> None:
    currency, _, events, projector = _currency()
    events.append(
        REFERENCE_DOCUMENT_CHANGED,
        "doc-1",
        reference_document_state_to_payload(replace(STATE, review_due_on=date(2026, 10, 1))),
    )
    events.append(
        REFERENCE_DOCUMENT_CHANGED,
        "doc-2",
        reference_document_state_to_payload(
            replace(STATE, document_id="doc-2", review_due_on=date(2026, 12, 1))
        ),
    )
    while projector.project_next():
        pass
    assert currency.overdue_reviews(("doc-1", "doc-2", "unknown"), date(2026, 10, 6)) == {
        "doc-1": date(2026, 10, 1)
    }
    # The same copy, read later, finds the second one overdue too: nothing has to be sent.
    assert currency.overdue_reviews(["doc-1", "doc-2"], date(2026, 12, 1)) == {
        "doc-1": date(2026, 10, 1),
        "doc-2": date(2026, 12, 1),
    }
