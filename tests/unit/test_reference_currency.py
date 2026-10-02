"""Requirement work's local copy of the library's citable state (ADR-0099)."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import RLock

import pytest
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.errors import (
    PersistenceError,
    RequirementAnalysisConflictError,
)
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
from smb_requirement_agent.domain.document.errors import InvalidDocumentError
from smb_requirement_agent.domain.document.reference import (
    CurrentPublication,
    PublishedReference,
    ReferenceDocumentState,
    normalize_search,
)
from smb_requirement_agent.infrastructure.persistence.architecture_release_state import (
    InMemoryArchitectureReleaseState,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_transaction import (
    InMemoryTransactionManager,
)
from smb_requirement_agent.infrastructure.persistence.knowledge_events import (
    InMemoryKnowledgeEvents,
)
from smb_requirement_agent.infrastructure.persistence.reference_publications import (
    InMemoryReferencePublications,
)

NOW = datetime(2026, 10, 2, 9, tzinfo=UTC)
TEXT = "XGPON coverage is required."
PUBLISHED = CurrentPublication(
    "pub-1", "f" * 64, "ver-1", 1, "rev-1", (("b1", "Line 1"),), (("b1", TEXT),)
)
STATE = ReferenceDocumentState("doc-1", "owner", "Eligibility", 4, PUBLISHED)


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
    assert ReferenceDocumentState.from_payload(STATE.to_payload()) == STATE
    withdrawn = replace(STATE, published=None)
    assert ReferenceDocumentState.from_payload(withdrawn.to_payload()) == withdrawn
    assert withdrawn.publication_state == "4:withdrawn"
    assert STATE.publication_state == "4:pub-1"
    malformed: tuple[object, ...] = (
        {},
        {"document_id": 1},
        [],
        {**STATE.to_payload(), "published": {"x": 1}},
    )
    for payload in malformed:
        with pytest.raises(InvalidDocumentError):
            ReferenceDocumentState.from_payload(payload)


def _currency() -> tuple[
    ReferenceCurrency,
    InMemoryReferencePublications,
    InMemoryKnowledgeEvents,
    ProjectKnowledgeEvents,
]:
    lock = RLock()
    states = InMemoryReferencePublications(lock)
    events = InMemoryKnowledgeEvents(lock)
    transactions = InMemoryTransactionManager(lambda _: None, lock)
    transactions.enroll(states, events)
    projector = ProjectKnowledgeEvents(
        events, states, InMemoryArchitectureReleaseState(lock), transactions, FixedClock(NOW)
    )
    return ReferenceCurrency(states, transactions), states, events, projector


def test_the_copy_catches_up_from_the_outbox_and_checks_citations_locally() -> None:
    currency, states, events, projector = _currency()
    events.append(REFERENCE_DOCUMENT_CHANGED, "doc-1", STATE.to_payload())
    with pytest.raises(RequirementAnalysisConflictError):
        currency.require_current((_citation(),))

    assert projector.project_next()
    currency.require_current((_citation(),))
    assert not projector.project_next()

    events.append(REFERENCE_DOCUMENT_CHANGED, "doc-1", replace(STATE, published=None).to_payload())
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
        payload = STATE.to_payload()
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
    )

    projector.project_next()

    # Every visible event is applied either way; only the cursor waits.
    assert states.get("doc-1") is not None
    assert states.cursor() == cursor


def test_the_active_release_follows_activation_events_and_never_goes_back() -> None:
    lock = RLock()
    events = InMemoryKnowledgeEvents(lock)
    releases = InMemoryArchitectureReleaseState(lock)
    transactions = InMemoryTransactionManager(lambda _: None, lock)
    transactions.enroll(events, releases)
    projector = ProjectKnowledgeEvents(
        events, InMemoryReferencePublications(lock), releases, transactions, FixedClock(NOW)
    )
    current = CurrentArchitectureRelease(releases)
    with pytest.raises(PersistenceError, match="No active architecture release"):
        current.active_release_id()

    events.append(ARCHITECTURE_RELEASE_ACTIVATED, "r1", {"release_id": "r1"})
    events.append(ARCHITECTURE_RELEASE_ACTIVATED, "r2", {"release_id": "r2"})
    projector.drain()
    assert current.active_release_id() == "r2"
    releases.apply(1, "r1")
    assert current.active_release_id() == "r2"

    events.append(ARCHITECTURE_RELEASE_ACTIVATED, "r3", {"release": "malformed"})
    with pytest.raises(PersistenceError, match="malformed"):
        projector.drain()
    assert current.active_release_id() == "r2"
