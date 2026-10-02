"""Requirement work's HTTP adapters against the knowledge service's real internal API (ADR-0099).

The knowledge internal API is served from the same container as the in-process
objects, so every answer over HTTP must equal the in-process one exactly.
"""

from __future__ import annotations

from collections.abc import Iterator
from threading import RLock
from typing import Any, cast

import httpx
import pytest
from fastapi.testclient import TestClient
from smb_kernel.errors import ServiceResponseError, ServiceUnavailableError
from smb_kernel.http.client import InternalHttpClient
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgePort,
    ArchitectureQuery,
)
from smb_requirement_agent.application.ports.knowledge_events import KnowledgeEventSourcePort
from smb_requirement_agent.application.ports.reference_grounding import ReferenceKnowledgePort
from smb_requirement_agent.application.use_cases.document_library import LibraryView
from smb_requirement_agent.application.use_cases.reference_currency import (
    ProjectKnowledgeEvents,
    ReferenceCurrency,
)
from smb_requirement_agent.infrastructure.knowledge_client import (
    FakeArchitectureKnowledge,
    FakeKnowledgeEvents,
    FakeReferenceKnowledge,
    HttpArchitectureKnowledge,
    HttpKnowledgeEvents,
    HttpReferenceKnowledge,
)
from smb_requirement_agent.infrastructure.persistence.architecture_release_state import (
    InMemoryArchitectureReleaseState,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_transaction import (
    InMemoryTransactionManager,
)
from smb_requirement_agent.infrastructure.persistence.reference_publications import (
    InMemoryReferencePublications,
)
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.interfaces.knowledge_internal.app import create_knowledge_internal_app
from tests.unit import test_reference_grounding

grounded = test_reference_grounding.grounded
# TestClient ignores per-request timeouts; the kernel client always sends one.
pytestmark = pytest.mark.filterwarnings("ignore:You should not use the 'timeout' argument")


def _as_httpx(client: TestClient) -> httpx.Client:
    """TestClient serves the same request API; it is typed on Starlette's own httpx build."""
    return cast(httpx.Client, client)


TOKEN = "r" * 40
QUERY = "XGPON coverage for high-speed bundles"


@pytest.fixture
def served(
    grounded: tuple[Container, LibraryView],
) -> Iterator[tuple[Container, InternalHttpClient]]:
    container, _ = grounded
    app = create_knowledge_internal_app(lambda: container, TOKEN)
    with TestClient(app) as http:
        yield (
            container,
            InternalHttpClient(
                "http://testserver", TOKEN, service="knowledge", http=_as_httpx(http), retries=0
            ),
        )


def test_reference_answers_over_http_equal_the_in_process_ones(
    served: tuple[Container, InternalHttpClient],
) -> None:
    container, client = served
    references = HttpReferenceKnowledge(client)
    assert references.has_published() is True
    assert references.search_evidence(QUERY) == container.reference_knowledge.search_evidence(QUERY)
    assert references.retrieve(QUERY) == container.reference_knowledge.retrieve(QUERY)
    assert references.search_evidence(QUERY)


def test_architecture_matches_over_http_equal_the_in_process_ones(
    served: tuple[Container, InternalHttpClient],
) -> None:
    container, client = served
    query = ArchitectureQuery(("Order a bundle through the assisted channel.",), ("BCRM", "CPP"))
    assert HttpArchitectureKnowledge(client).match(query) == container.architecture_knowledge.match(
        query
    )


def test_a_local_copy_fed_only_over_http_equals_the_in_process_one(
    served: tuple[Container, InternalHttpClient],
) -> None:
    container, client = served
    events = HttpKnowledgeEvents(client)
    in_process = container.knowledge_events.after(0, 500)
    assert events.after(0, 500) == in_process and in_process

    lock = RLock()
    states = InMemoryReferencePublications(lock)
    releases = InMemoryArchitectureReleaseState(lock)
    transactions = InMemoryTransactionManager(lambda _: None, lock)
    transactions.enroll(states, releases)
    ProjectKnowledgeEvents(
        events, states, releases, transactions, FixedClock(in_process[-1].created_at)
    ).drain()
    # The HTTP-fed copy accepts exactly the citations the library considers current.
    citations = tuple(
        item.citation for item in container.reference_knowledge.search_evidence(QUERY)
    )
    assert citations
    ReferenceCurrency(states, transactions).require_current(citations)
    assert releases.active_release_id() is not None


def test_a_wrong_token_is_refused(served: tuple[Container, InternalHttpClient]) -> None:
    container, _ = served
    app = create_knowledge_internal_app(lambda: container, TOKEN)
    with TestClient(app) as http:
        wrong = InternalHttpClient(
            "http://testserver", "w" * 40, service="knowledge", http=_as_httpx(http), retries=0
        )
        with pytest.raises(ServiceResponseError) as refused:
            HttpReferenceKnowledge(wrong).has_published()
    assert refused.value.status_code == 401


def _answering(body: Any) -> InternalHttpClient:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=body))
    return InternalHttpClient(
        "http://knowledge", TOKEN, service="knowledge", http=httpx.Client(transport=transport)
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda c: HttpReferenceKnowledge(c).has_published(),
        lambda c: HttpReferenceKnowledge(c).search_evidence("q"),
        lambda c: HttpReferenceKnowledge(c).retrieve("q"),
        lambda c: HttpArchitectureKnowledge(c).match(ArchitectureQuery(("text",))),
        lambda c: HttpKnowledgeEvents(c).after(0, 10),
    ],
)
@pytest.mark.parametrize(
    "body",
    [
        {"unexpected": True},
        [{"citation": {"document_id": " "}}],
        [{"seq": 2, "kind": "k", "subject_id": "s", "payload": {}, "created_at": "nope"}],
    ],
)
def test_an_unusable_answer_is_an_explicit_failure(call: Any, body: Any) -> None:
    with pytest.raises(ServiceUnavailableError):
        call(_answering(body))


def test_events_out_of_order_are_refused() -> None:
    body = [
        {
            "seq": 3,
            "kind": "k",
            "subject_id": "s",
            "payload": {},
            "created_at": "2026-10-02T00:00:00+00:00",
        },
        {
            "seq": 2,
            "kind": "k",
            "subject_id": "s",
            "payload": {},
            "created_at": "2026-10-02T00:00:00+00:00",
        },
    ]
    with pytest.raises(ServiceUnavailableError, match="out of order"):
        HttpKnowledgeEvents(_answering(body)).after(0, 10)


def test_the_fakes_stand_in_for_each_port_deterministically() -> None:
    architecture: ArchitectureKnowledgePort = FakeArchitectureKnowledge()
    references: ReferenceKnowledgePort = FakeReferenceKnowledge()
    events: KnowledgeEventSourcePort = FakeKnowledgeEvents()
    match = architecture.match(ArchitectureQuery(("text",), release_id="r1"))
    assert (match.knowledge_version, match.systems, match.dependencies) == ("r1", (), ())
    assert match == architecture.match(ArchitectureQuery(("text",), release_id="r1"))
    assert not references.has_published()
    assert references.search_evidence("q") == () and references.retrieve("q") == ()
    assert events.after(0, 10) == ()
