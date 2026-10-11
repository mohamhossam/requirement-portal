"""Requirement work's HTTP adapters onto the knowledge service (ADR-0099).

The adapters are held to the pinned `contracts/knowledge-internal.openapi.json`:
every request they send is a route of the contract, with its parameters, its
body and the service token; every contract-shaped answer decodes into equal
contract values; anything else fails as an explicit adapter error.
knowledge-portal serves and tests those routes against the same file.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from smb_kernel.errors import ServiceResponseError, ServiceUnavailableError
from smb_kernel.http.client import InternalHttpClient

from smb_requirement_agent.breakdown.domain.architecture.entities import ArchitectureImpact
from smb_requirement_agent.references.application.ports.architecture_assessment import (
    ArchitectureAssessment,
    AssessedComponent,
    AssessedConcept,
    AssessedCoverage,
    AssessedFacet,
    AssessedGap,
    AssessedOption,
    AssessedOwners,
    AssessedPathStep,
    AssessedProposal,
    AssessedQuestion,
    AssessedReference,
    AssessedSeat,
    AssessedSystem,
    AssessmentQuery,
)
from smb_requirement_agent.references.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureKnowledgePort,
    ArchitectureQuery,
)
from smb_requirement_agent.references.application.ports.historic_corpus import (
    ContentPart,
    HistoricContentGoneError,
)
from smb_requirement_agent.references.application.ports.knowledge_events import (
    ARCHITECTURE_RELEASE_ACTIVATED,
    REFERENCE_DOCUMENT_CHANGED,
    KnowledgeEvent,
    KnowledgeEventSourcePort,
)
from smb_requirement_agent.references.application.ports.reference_grounding import (
    ReferenceEvidence,
    ReferenceKnowledgePort,
)
from smb_requirement_agent.references.domain.architecture.catalogue import (
    ArchitectureCitation,
    ArchitectureDependency,
    DomainSuggestion,
    JourneyNeighbour,
    JourneyStep,
    OfferingDuty,
    OrganisationReference,
    ProductContext,
    SystemCapability,
    SystemReference,
)
from smb_requirement_agent.references.domain.architecture.knowledge import RelationshipKind
from smb_requirement_agent.references.infrastructure.knowledge_client import (
    OFFLINE_RELEASE_ID,
    OFFLINE_RELEASE_NAME,
    FakeArchitectureAssessment,
    FakeArchitectureKnowledge,
    FakeKnowledgeEvents,
    FakeReferenceKnowledge,
    HttpArchitectureAssessment,
    HttpArchitectureKnowledge,
    HttpChangeRequestInbox,
    HttpDeliveryInbox,
    HttpHistoricContent,
    HttpKnowledgeEvents,
    HttpPrecedentInbox,
    HttpReferenceKnowledge,
)
from smb_requirement_agent.shared_kernel.citation import PublishedReference
from tests.unit.analysis.test_product_impact import DRAFTED_OFFERING
from tests.unit.workflow_helpers import approve_fake_breakdown

CONTRACT = json.loads(
    (Path(__file__).parents[2] / "contracts" / "knowledge-internal.openapi.json").read_text(
        encoding="utf-8"
    )
)
SCHEMAS: dict[str, Any] = CONTRACT["components"]["schemas"]
TOKEN = "r" * 40
QUERY = "XGPON coverage for high-speed bundles"
SHA = "a" * 64

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler, seen: list[httpx.Request] | None = None) -> InternalHttpClient:
    def record(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return handler(request)

    return InternalHttpClient(
        "http://knowledge",
        TOKEN,
        service="knowledge",
        http=httpx.Client(transport=httpx.MockTransport(record)),
        retries=0,
    )


def _answering(body: Any, status: int = 200) -> Handler:
    return lambda _request: httpx.Response(status, json=body)


def _violations(
    value: Any, schema: dict[str, Any], at: str = "body", *, open_objects: bool = False
) -> list[str]:
    """Where `value` departs from a contract schema, including fields it does not list
    (unless `open_objects`: a route that reads a subset and ignores the rest)."""
    if "$ref" in schema:
        schema = SCHEMAS[schema["$ref"].rsplit("/", 1)[-1]]
    if "anyOf" in schema:
        options = [
            _violations(value, option, at, open_objects=open_objects) for option in schema["anyOf"]
        ]
        return [] if any(not found for found in options) else [f"{at}: matches no option"]
    if "enum" in schema:
        return [] if value in schema["enum"] else [f"{at}: {value!r} is not allowed"]
    kind = schema.get("type")
    checks: dict[str, Callable[[Any], bool]] = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "null": lambda v: v is None,
    }
    if kind in checks and not checks[kind](value):
        return [f"{at}: expected {kind}"]
    found: list[str] = []
    if kind == "string" and not schema.get("minLength", 0) <= len(value) <= schema.get(
        "maxLength", len(value)
    ):
        found.append(f"{at}: length out of bounds")
    if kind == "array":
        for index, item in enumerate(value):
            found += _violations(
                item, schema.get("items", {}), f"{at}[{index}]", open_objects=open_objects
            )
    if kind == "object":
        properties = schema.get("properties", {})
        found += [
            f"{at}.{name}: missing" for name in schema.get("required", ()) if name not in value
        ]
        for name, item in value.items():
            if name in properties:
                found += _violations(
                    item, properties[name], f"{at}.{name}", open_objects=open_objects
                )
            elif not (open_objects or schema.get("additionalProperties")):
                found.append(f"{at}.{name}: not in the contract")
    return found


def _operation(request: httpx.Request) -> dict[str, Any]:
    # The raw path: an escaped slash inside an id must stay one path segment.
    path = request.url.raw_path.split(b"?")[0].decode()
    for template, item in CONTRACT["paths"].items():
        pattern = "^" + re.sub(r"\{[^}]+\}", "[^/]+", template) + "$"
        if re.match(pattern, path) and request.method.lower() in item:
            operation: dict[str, Any] = item[request.method.lower()]
            return operation
    raise AssertionError(f"{request.method} {path} is not in the contract.")


def _assert_in_contract(request: httpx.Request) -> None:
    operation = _operation(request)
    parameters = operation.get("parameters", ())
    query = {p["name"] for p in parameters if p["in"] == "query"}
    required = {p["name"] for p in parameters if p["in"] == "query" and p["required"]}
    sent = set(request.url.params.keys())
    assert sent <= query and required <= sent, (sent, query, required)
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    body = operation.get("requestBody")
    if body is None:
        assert not request.content
    else:
        schema = body["content"]["application/json"]["schema"]
        assert _violations(json.loads(request.content), schema) == []


def _assert_answer_in_contract(request: httpx.Request, answer: Any) -> None:
    """The canned answer is one the contract allows, so the decoding tested is real."""
    response = _operation(request)["responses"]["200"]["content"]["application/json"]
    assert _violations(answer, response["schema"], "answer") == []


MATCH = {
    "knowledge_version": "rel-7",
    "systems": [
        {
            "id": "bcrm",
            "name": "BCRM",
            "catalogued": True,
            "capabilities": [
                {
                    "id": "assisted-sales",
                    "name": "Assisted sales",
                    "domain_id": "sales",
                    "domain_path": ["Sales", "Assisted"],
                    "component_id": "orders",
                    "component_name": "Order capture",
                }
            ],
            "constraints": ["Runs nightly"],
            "squads": [{"id": "sq-1", "name": "Ordering squad"}],
            "value_streams": [{"id": "vs-1", "name": "Order to activate"}],
            "products": [],
        },
        {"id": "cpp", "name": "CPP", "catalogued": False},
    ],
    "dependencies": [
        {
            "source_system_id": "bcrm",
            "target_system_id": "cpp",
            "description": "BCRM orders through CPP.",
            "kind": "calls_api",
        }
    ],
    "citation_ids": ["chunk-1"],
    "uncertainty": "CPP is not catalogued.",
    "model": "reasoner-1",
    "embedding_model": "embedder-1",
    "prompt_version": "architecture-impact-v1",
    "index_revision": 3,
    "evidence_classification": "ai_inference",
    "citations": [{"system_id": "bcrm", "chunk_id": "chunk-1", "quote": "BCRM orders bundles."}],
    "adjacent_systems": [{"id": "billing", "name": "Billing", "catalogued": True}],
    "adjacent_dependencies": [
        {
            "source_system_id": "cpp",
            "target_system_id": "billing",
            "description": "CPP bills orders.",
            "kind": "unspecified",
        }
    ],
    "adjacent_omitted": 2,
    "suggested_domains": [
        {
            "domain_id": "sales",
            "path": ["Sales"],
            "system_ids": ["bcrm"],
            "matched_terms": ["ordering"],
            "system_names": ["BCRM"],
        }
    ],
    "product_contexts": [
        {
            "product_id": "fibre",
            "product_name": "Business fibre",
            "matched_terms": ["fibre"],
            "order_type": "new",
            "responsibilities": [
                {
                    "component_id": "line",
                    "component_name": "Access line",
                    "system_id": "bcrm",
                    "system_name": "BCRM",
                    "role": "captures",
                    "description": "Captures the order.",
                }
            ],
        }
    ],
    "journey_steps": [
        {
            "system_id": "bcrm",
            "journey_id": "j-1",
            "journey_name": "Order to activate",
            "number": "2",
            "name": "Capture order",
            "performs": True,
            "fulfils": ["Business fibre"],
            "before": [{"number": "1", "name": "Qualify"}],
            "after": [
                {"number": "3", "name": "Activate", "system_id": "cpp", "system_name": "CPP"}
            ],
        }
    ],
}
EXPECTED_MATCH = ArchitectureKnowledgeMatch(
    "rel-7",
    (
        SystemReference(
            "bcrm",
            "BCRM",
            True,
            (
                SystemCapability(
                    "assisted-sales",
                    "Assisted sales",
                    "sales",
                    ("Sales", "Assisted"),
                    "orders",
                    "Order capture",
                ),
            ),
            ("Runs nightly",),
            (OrganisationReference("sq-1", "Ordering squad"),),
            (OrganisationReference("vs-1", "Order to activate"),),
        ),
        SystemReference("cpp", "CPP", False),
    ),
    (
        ArchitectureDependency(
            "bcrm", "cpp", "BCRM orders through CPP.", RelationshipKind.CALLS_API
        ),
    ),
    ("chunk-1",),
    "CPP is not catalogued.",
    "reasoner-1",
    "embedder-1",
    "architecture-impact-v1",
    3,
    "ai_inference",
    (ArchitectureCitation("bcrm", "chunk-1", "BCRM orders bundles."),),
    (SystemReference("billing", "Billing", True),),
    (ArchitectureDependency("cpp", "billing", "CPP bills orders."),),
    2,
    (DomainSuggestion("sales", ("Sales",), ("bcrm",), ("ordering",), ("BCRM",)),),
    (
        ProductContext(
            "fibre",
            "Business fibre",
            ("fibre",),
            "new",
            (
                OfferingDuty(
                    "line", "Access line", "bcrm", "BCRM", "captures", "Captures the order."
                ),
            ),
        ),
    ),
    (
        JourneyStep(
            "bcrm",
            "j-1",
            "Order to activate",
            "2",
            "Capture order",
            True,
            ("Business fibre",),
            (JourneyNeighbour("1", "Qualify"),),
            (JourneyNeighbour("3", "Activate", "cpp", "CPP"),),
        ),
    ),
)

EXCERPT = "XGPON coverage is required."
EVIDENCE = [
    {
        "citation": {
            "document_id": "doc/1",
            "title": "Eligibility policy",
            "version_id": "ver-1",
            "version_number": 2,
            "revision_id": "rev-1",
            "publication_id": "pub-1",
            "approval_fingerprint": SHA,
            "block_id": "block-1",
            "location": "Paragraph 3",
            "excerpt": EXCERPT,
            "start_offset": 10,
            "end_offset": 10 + len(EXCERPT),
            "lineage_hash": "b" * 64,
        },
        "context_text": "Eligibility. XGPON coverage is required.",
        "context_locations": ["Paragraph 2", "Paragraph 3"],
    }
]
EXPECTED_EVIDENCE = (
    ReferenceEvidence(
        PublishedReference(
            "doc/1",
            "Eligibility policy",
            "ver-1",
            2,
            "rev-1",
            "pub-1",
            SHA,
            "block-1",
            "Paragraph 3",
            EXCERPT,
            10,
            10 + len(EXCERPT),
            "b" * 64,
        ),
        "Eligibility. XGPON coverage is required.",
        ("Paragraph 2", "Paragraph 3"),
    ),
)

EVENTS = [
    {
        "seq": 4,
        "kind": ARCHITECTURE_RELEASE_ACTIVATED,
        "subject_id": "rel-7",
        "payload": {"release_id": "rel-7", "name": "October update"},
        "created_at": "2026-10-02T09:00:00+00:00",
    },
    {
        "seq": 6,
        "kind": REFERENCE_DOCUMENT_CHANGED,
        "subject_id": "doc/1",
        "payload": {"document_id": "doc/1", "version": 3, "published": None},
        "created_at": "2026-10-02T09:05:00+00:00",
    },
]
EXPECTED_EVENTS = (
    KnowledgeEvent(
        4,
        ARCHITECTURE_RELEASE_ACTIVATED,
        "rel-7",
        {"release_id": "rel-7", "name": "October update"},
        datetime(2026, 10, 2, 9, tzinfo=UTC),
    ),
    KnowledgeEvent(
        6,
        REFERENCE_DOCUMENT_CHANGED,
        "doc/1",
        {"document_id": "doc/1", "version": 3, "published": None},
        datetime(2026, 10, 2, 9, 5, tzinfo=UTC),
    ),
)


@pytest.mark.parametrize(
    ("query", "body"),
    [
        pytest.param(
            ArchitectureQuery(("Order a bundle.", "Activate it."), ("BCRM", "CPP"), "rel-7"),
            {
                "text": ["Order a bundle.", "Activate it."],
                "declared_systems": ["BCRM", "CPP"],
                "release_id": "rel-7",
            },
            id="pinned",
        ),
        pytest.param(
            ArchitectureQuery(("Order a bundle.",)),
            {"text": ["Order a bundle."], "declared_systems": [], "release_id": None},
            id="active release",
        ),
    ],
)
def test_an_architecture_query_is_sent_as_the_contract_describes(
    query: ArchitectureQuery, body: dict[str, Any]
) -> None:
    seen: list[httpx.Request] = []

    HttpArchitectureKnowledge(_client(_answering(MATCH), seen)).match(query)

    (request,) = seen
    _assert_in_contract(request)
    assert (request.method, request.url.path) == ("POST", "/internal/architecture/match")
    assert json.loads(request.content) == body


def test_a_contract_shaped_match_decodes_into_equal_values() -> None:
    seen: list[httpx.Request] = []

    match = HttpArchitectureKnowledge(_client(_answering(MATCH), seen)).match(
        ArchitectureQuery(("Order a bundle.",), ("BCRM", "CPP"), "rel-7")
    )

    _assert_answer_in_contract(seen[0], MATCH)
    assert match == EXPECTED_MATCH


def test_a_minimal_match_takes_the_contract_defaults() -> None:
    minimal = {"knowledge_version": "rel-7", "systems": [], "dependencies": []}
    seen: list[httpx.Request] = []

    match = HttpArchitectureKnowledge(_client(_answering(minimal), seen)).match(
        ArchitectureQuery(("text",))
    )

    _assert_answer_in_contract(seen[0], minimal)
    assert match == ArchitectureKnowledgeMatch("rel-7", (), ())


@pytest.mark.parametrize("published", [True, False])
def test_whether_anything_is_published_is_read_from_the_library(published: bool) -> None:
    seen: list[httpx.Request] = []
    answer = {"has_published": published}

    found = HttpReferenceKnowledge(_client(_answering(answer), seen)).has_published()

    (request,) = seen
    _assert_in_contract(request)
    _assert_answer_in_contract(request, answer)
    assert (request.method, request.url.path) == ("GET", "/internal/library/published")
    assert found is published


@pytest.mark.parametrize(
    ("call", "path"),
    [
        pytest.param(lambda r: r.search_evidence(QUERY), "/internal/library/search", id="search"),
        pytest.param(lambda r: r.retrieve(QUERY), "/internal/library/retrieve", id="retrieve"),
    ],
)
def test_library_evidence_is_asked_for_and_decoded_as_the_contract_describes(
    call: Callable[[HttpReferenceKnowledge], tuple[ReferenceEvidence, ...]], path: str
) -> None:
    seen: list[httpx.Request] = []

    found = call(HttpReferenceKnowledge(_client(_answering(EVIDENCE), seen)))

    (request,) = seen
    _assert_in_contract(request)
    _assert_answer_in_contract(request, EVIDENCE)
    assert (request.method, request.url.path) == ("POST", path)
    assert json.loads(request.content) == {"query": QUERY}
    assert found == EXPECTED_EVIDENCE


def test_events_are_read_after_a_cursor_and_decoded_in_order() -> None:
    seen: list[httpx.Request] = []

    events = HttpKnowledgeEvents(_client(_answering(EVENTS), seen)).after(3, 50)

    (request,) = seen
    _assert_in_contract(request)
    _assert_answer_in_contract(request, EVENTS)
    assert (request.method, request.url.path) == ("GET", "/internal/events")
    assert dict(request.url.params) == {"after": "3", "limit": "50"}
    assert events == EXPECTED_EVENTS
    assert HttpKnowledgeEvents(_client(_answering([]))).after(6, 50) == ()


CALLS = [
    pytest.param(lambda c: HttpReferenceKnowledge(c).has_published(), id="published"),
    pytest.param(lambda c: HttpReferenceKnowledge(c).search_evidence("q"), id="search"),
    pytest.param(lambda c: HttpReferenceKnowledge(c).retrieve("q"), id="retrieve"),
    pytest.param(
        lambda c: HttpArchitectureKnowledge(c).match(ArchitectureQuery(("text",))), id="match"
    ),
    pytest.param(lambda c: HttpKnowledgeEvents(c).after(0, 10), id="events"),
]


@pytest.mark.parametrize("call", CALLS)
@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"unexpected": True}, id="wrong shape"),
        pytest.param([{"citation": {"document_id": " "}}], id="blank citation"),
        pytest.param(
            [{"seq": 2, "kind": "k", "subject_id": "s", "payload": {}, "created_at": "nope"}],
            id="bad timestamp",
        ),
        pytest.param(
            {**MATCH, "systems": [{"id": " ", "name": "BCRM", "catalogued": True}]},
            id="domain invariant",
        ),
        pytest.param(
            [{**EVENTS[0], "seq": 0}],
            id="cursor below one",
        ),
    ],
)
def test_an_unusable_answer_is_an_explicit_failure(
    call: Callable[[InternalHttpClient], object], body: Any
) -> None:
    with pytest.raises(ServiceUnavailableError):
        call(_client(_answering(body)))


@pytest.mark.parametrize("call", CALLS)
def test_a_refused_token_is_a_service_response_error(
    call: Callable[[InternalHttpClient], object],
) -> None:
    refused = _client(_answering({"detail": "Invalid service token."}, status=401))

    with pytest.raises(ServiceResponseError) as raised:
        call(refused)

    assert raised.value.status_code == 401


@pytest.mark.parametrize(
    "seqs", [pytest.param((3, 2), id="backwards"), pytest.param((3, 3), id="repeated")]
)
def test_events_out_of_order_are_refused(seqs: tuple[int, int]) -> None:
    body = [{**EVENTS[0], "seq": seqs[0]}, {**EVENTS[1], "seq": seqs[1]}]

    with pytest.raises(ServiceUnavailableError, match="out of order"):
        HttpKnowledgeEvents(_client(_answering(body))).after(0, 10)


def test_the_fakes_stand_in_for_each_port_deterministically() -> None:
    architecture: ArchitectureKnowledgePort = FakeArchitectureKnowledge()
    references: ReferenceKnowledgePort = FakeReferenceKnowledge()
    events: KnowledgeEventSourcePort = FakeKnowledgeEvents()

    pinned = architecture.match(
        ArchitectureQuery(("BCRM and CPP",), ("BCRM", " CPP ", "bcrm", ""), release_id="r1")
    )
    assert (pinned.knowledge_version, pinned.dependencies) == ("r1", ())
    # Only what the Requirement declares, once each and never catalogued: the
    # text names systems too, but there is no catalogue to match it against.
    assert [(item.name, item.catalogued) for item in pinned.systems] == [
        ("BCRM", False),
        ("CPP", False),
    ]
    assert pinned == architecture.match(
        ArchitectureQuery(("BCRM and CPP",), ("BCRM", " CPP ", "bcrm", ""), release_id="r1")
    )
    assert architecture.match(ArchitectureQuery(("BCRM",))).systems == ()
    unpinned = architecture.match(ArchitectureQuery(("text",)))
    assert unpinned.knowledge_version == OFFLINE_RELEASE_ID
    # Nothing was inferred, and the empty answer is one a backlog item can carry.
    assert unpinned.evidence_classification == "legacy_deterministic"
    ArchitectureImpact(
        unpinned.knowledge_version,
        datetime(2026, 10, 2, tzinfo=UTC),
        unpinned.systems,
        unpinned.dependencies,
        uncertainty=unpinned.uncertainty,
        evidence_classification=unpinned.evidence_classification,
    )
    assert not references.has_published()
    assert references.search_evidence("q") == () and references.retrieve("q") == ()

    # The offline service has activated one empty catalogue version, once.
    (activation,) = events.after(0, 10)
    assert (activation.seq, activation.kind, activation.subject_id) == (
        1,
        ARCHITECTURE_RELEASE_ACTIVATED,
        OFFLINE_RELEASE_ID,
    )
    assert activation.payload == {"release_id": OFFLINE_RELEASE_ID, "name": OFFLINE_RELEASE_NAME}
    assert events.after(0, 10) == (activation,)
    assert events.after(1, 10) == ()
    assert events.after(0, 0) == ()


def test_an_approved_backlog_is_delivered_as_the_contract_describes(client: TestClient) -> None:
    requirement_id, _, revision = approve_fake_breakdown(client)
    export = json.loads(
        client.get(
            f"/requirements/{requirement_id}/revisions/{revision}/export?format=json"
        ).content
    )
    export["manifest"]["final_approval"]["recorded_by"]["email"] = None
    receipt = {
        "change_request_id": "CR-20261005-Portable_backlog",
        "approval_id": export["manifest"]["final_approval"]["id"],
        "created": True,
    }
    seen: list[httpx.Request] = []

    delivered = HttpChangeRequestInbox(_client(_answering(receipt, 201), seen)).deliver(export)

    assert delivered == "CR-20261005-Portable_backlog"
    (request,) = seen
    assert (request.method, request.url.path) == ("POST", "/internal/change-requests")
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    operation = _operation(request)
    schema = operation["requestBody"]["content"]["application/json"]["schema"]
    # The route reads a bounded subset of the export (schema 1.x) and ignores the rest.
    assert _violations(json.loads(request.content), schema, open_objects=True) == []
    answer = operation["responses"]["201"]["content"]["application/json"]["schema"]
    assert _violations(receipt, answer, "answer") == []
    # A replay of the same approval answers 200 with the same change request.
    assert "200" in operation["responses"]


def test_a_drafted_offering_is_delivered_as_the_contract_describes() -> None:
    """Export schema 1.6 sends the decided product impact, with the drafted offering back
    exactly as the assessment answered it (ontology plan Phase 9)."""
    product = {
        "verdict": "new_product_line",
        "offering_id": "offering:fiber",
        "release_id": "rel-7",
        "draft": DRAFTED_OFFERING,
    }
    schema = SCHEMAS["ApprovedBacklogRequest"]["properties"]["product_impact"]

    assert _violations(product, schema, "product_impact") == []


def test_a_refused_or_unusable_delivery_is_an_explicit_failure() -> None:
    refused = HttpChangeRequestInbox(_client(_answering({"detail": "Another subject."}, 409)))
    with pytest.raises(ServiceResponseError) as raised:
        refused.deliver({"schema_version": "1.6"})
    assert raised.value.status_code == 409
    for answer in ({"approval_id": "apr-1"}, ["CR-1"], {"change_request_id": 7}):
        with pytest.raises(ServiceUnavailableError):
            HttpChangeRequestInbox(_client(_answering(answer, 201))).deliver({})


# --- Decided verdicts kept as precedents (ontology plan Phase 5) ---------------------------

PRECEDENT = {
    "precedent_id": "ANA-1",
    "requirement_id": "REQ-1",
    "version": "ANA-1@4",
    "release_id": "rel-7",
    "text": ["Static IP for SMB fibre.", "Customers keep their address."],
    "decision": "overridden",
    "decided_at": "2026-10-11T09:00:00+00:00",
    "suggested_verdict": "change_existing_offering",
    "verdict": "new_plan",
    "offering_id": "offering:fiber",
    "concept_ids": ["cap:ip"],
    "systems": [{"id": "bcrm", "role": "primary", "change_type": "modify"}],
}


def test_a_decided_verdict_is_delivered_as_the_contract_describes() -> None:
    receipt = {"precedent_id": "ANA-1", "recorded": True, "dropped_systems": []}
    seen: list[httpx.Request] = []

    recorded = HttpPrecedentInbox(_client(_answering(receipt, 201), seen)).record(PRECEDENT)

    assert recorded is True
    (request,) = seen
    _assert_in_contract(request)
    assert (request.method, request.url.path) == ("POST", "/internal/architecture/precedents")
    operation = _operation(request)
    answer = operation["responses"]["201"]["content"]["application/json"]["schema"]
    assert _violations(receipt, answer, "answer") == []
    # The same decision, or a later one, already kept answers 200, not recorded.
    assert "200" in operation["responses"]
    kept = {**receipt, "recorded": False}
    assert HttpPrecedentInbox(_client(_answering(kept))).record(PRECEDENT) is False


def test_a_refused_or_unusable_precedent_receipt_is_an_explicit_failure() -> None:
    refused = HttpPrecedentInbox(_client(_answering({"detail": "No published release."}, 404)))
    with pytest.raises(ServiceResponseError) as raised:
        refused.record(PRECEDENT)
    assert raised.value.status_code == 404
    for answer in ({"precedent_id": "ANA-1"}, ["ANA-1"], {"recorded": "yes"}):
        with pytest.raises(ServiceUnavailableError):
            HttpPrecedentInbox(_client(_answering(answer, 201))).record(PRECEDENT)


# --- What a closed Epic delivered (ontology plan Phase 7) ----------------------------------

CLOSURE = {
    "delivery_id": "REQ-1:4711:evt-1",
    "state": "closed",
    "requirement_id": "REQ-1",
    "breakdown_revision": 2,
    "approval_id": "APR-9",
    "epic": {
        "id": "EP-1",
        "name": "Static IP quota",
        "external_id": "4711",
        "url": "https://dev.azure.com/acme/smb/_workitems/edit/4711",
    },
    "occurred_at": "2026-10-20T15:30:00+00:00",
    "release_id": "rel-7",
    "impact_version": "ANA-1@7",
    "decision": "accepted",
    "suggested_verdict": "change_existing_offering",
    "verdict": "change_existing_offering",
    "offering_id": "offering:fiber",
    "offering_name": "Business Fiber",
    "predicted_systems": [
        {"id": "bcrm", "name": "BCRM", "role": "primary", "change_type": "modify"}
    ],
    "features": [
        {
            "id": "FT-1",
            "sequence": 1,
            "name": "Order a static IP",
            "outcome": None,
            "external_id": "4712",
            "state": "Closed",
            "delivered": True,
            "systems": [{"id": "bcrm", "name": "BCRM"}, {"id": None, "name": "New portal"}],
        }
    ],
    "changes": [
        {
            "op": "realise_concept",
            "concept_id": "cap:static-ip",
            "concept_label": "Static IP",
            "system_id": "bcrm",
            "system_name": "BCRM",
            "feature_ids": ["FT-1"],
        },
        {
            "op": "offer_concept",
            "concept_id": "cap:static-ip",
            "concept_label": "Static IP",
            "offering_id": "offering:fiber",
            "offering_name": "Business Fiber",
            "feature_ids": ["FT-1"],
        },
    ],
}


def test_a_closed_epic_is_delivered_as_the_contract_describes() -> None:
    receipt = {"change_request_id": "CR-1", "created": True, "withdrawn": []}
    seen: list[httpx.Request] = []

    kept = HttpDeliveryInbox(_client(_answering(receipt, 201), seen)).deliver(CLOSURE)

    assert (kept.change_request_id, kept.withdrawn) == ("CR-1", ())
    (request,) = seen
    _assert_in_contract(request)
    assert (request.method, request.url.path) == ("POST", "/internal/change-requests/deliveries")
    operation = _operation(request)
    answer = operation["responses"]["201"]["content"]["application/json"]["schema"]
    assert _violations(receipt, answer, "answer") == []
    # Kept before, or a removal, answers 200 with the same receipt.
    assert "200" in operation["responses"]


def test_a_removed_epic_is_delivered_as_the_contract_describes() -> None:
    removed = {key: CLOSURE[key] for key in ("requirement_id", "breakdown_revision", "epic")}
    removed |= {
        "delivery_id": "REQ-1:4711:evt-2",
        "state": "removed",
        "approval_id": "APR-9",
        "occurred_at": "2026-10-21T08:00:00+00:00",
    }
    receipt = {"change_request_id": None, "created": False, "withdrawn": ["CR-1"]}
    seen: list[httpx.Request] = []

    answer = HttpDeliveryInbox(_client(_answering(receipt), seen)).deliver(removed)

    assert (answer.change_request_id, answer.withdrawn) == (None, ("CR-1",))
    _assert_in_contract(seen[0])


def test_a_refused_or_unusable_delivery_receipt_is_an_explicit_failure() -> None:
    refused = HttpDeliveryInbox(_client(_answering({"detail": "Another body."}, 409)))
    with pytest.raises(ServiceResponseError) as raised:
        refused.deliver(CLOSURE)
    assert raised.value.status_code == 409
    for answer in (
        ["CR-1"],
        {"change_request_id": 7, "withdrawn": []},
        {"change_request_id": "CR-1"},
        {"change_request_id": None, "withdrawn": [1]},
    ):
        with pytest.raises(ServiceUnavailableError):
            HttpDeliveryInbox(_client(_answering(answer, 201))).deliver(CLOSURE)


# --- A historic requirement's content, a page at a time (ADR-0102, amendment 1) ------------

HISTORIC_PAGE = {
    "historic_requirement_id": "h1",
    "publication": 2,
    "fingerprint": "f" * 64,
    "entries": [
        {
            "brd_id": "b1",
            "filename": "BRD-2025-014.docx",
            "block_id": "p1",
            "label": "Paragraph 1",
            "section_path": ["Scope"],
            "text": "Business customers order XGPON bundles.",
        }
    ],
    "next_offset": 200,
}


def test_historic_content_is_read_a_page_at_a_time_within_the_contract() -> None:
    seen: list[httpx.Request] = []
    page = HttpHistoricContent(_client(_answering(HISTORIC_PAGE), seen)).page(
        "h1", 2, ContentPart.PASSAGES, 0, 200
    )
    (request,) = seen
    _assert_in_contract(request)
    _assert_answer_in_contract(request, HISTORIC_PAGE)
    assert request.url.path == "/internal/historic-requirements/h1/passages"
    assert dict(request.url.params) == {"publication": "2", "offset": "0", "limit": "200"}
    assert (page.publication, page.next_offset, len(page.entries)) == (2, 200, 1)


@pytest.mark.parametrize("status", [404, 409])
def test_a_superseded_or_withdrawn_publication_is_gone_not_a_failure(status: int) -> None:
    gone = _client(_answering({"detail": "gone"}, status=status))
    with pytest.raises(HistoricContentGoneError):
        HttpHistoricContent(gone).page("h1", 1, ContentPart.ITEMS, 0, 200)


def test_an_unusable_historic_page_is_an_explicit_failure() -> None:
    with pytest.raises(ServiceUnavailableError):
        HttpHistoricContent(_client(_answering({"entries": "no"}))).page(
            "h1", 1, ContentPart.ITEMS, 0, 200
        )


ASSESSMENT = {
    "knowledge_version": "rel-7",
    "facets": [
        {
            "kind": "need",
            "text": "Static IP for SMB fibre",
            "quote": "static IP",
            "ref_id": None,
            "concepts": [
                {"concept_id": "cap:ip", "label": "Static IP", "path": "Net > IP", "weak": False}
            ],
        }
    ],
    "coverage": [
        {
            "concept_id": "cap:ip",
            "label": "Static IP",
            "path": "Net > IP",
            "composed_by": ["c1"],
            "realised_by": ["bcrm"],
            "covered": True,
        }
    ],
    "offering_id": "offering:fiber",
    "verdict": "change_existing_offering",
    "rule_verdict": "change_existing_offering",
    "verdict_reason": "Business Fiber covers it.",
    "proposal": {
        "summary": "Add a quota.",
        "offering_id": "offering:fiber",
        "portfolio_node_id": None,
        "components": [{"offering_id": "offering:fiber", "component_id": "c1", "name": "IP"}],
        "journey_ids": [],
        "new_values": ["Quota"],
    },
    "systems": [
        {
            "id": "bcrm",
            "name": "BCRM",
            "role": "primary",
            "change_type": "modify",
            "paths": [[{"kind": "system", "id": "bcrm", "label": "BCRM"}]],
        }
    ],
    "gaps": [
        {
            "kind": "staffing",
            "concept_id": "cap:ip",
            "label": "Static IP",
            "reason": "No squad.",
            "system_id": "bcrm",
        }
    ],
    "questions": [
        {
            "facet": "offering",
            "question": "Which offering?",
            "options": [{"id": "offering:fiber", "label": "Business Fiber"}],
        }
    ],
    "owners": [
        {
            "concept_id": "cap:ip",
            "system_id": "bcrm",
            "squads": [{"id": "sales", "name": "Sales"}],
            "value_streams": [],
            "seats": [
                {
                    "squad_id": "sales",
                    "role": "lead",
                    "person_id": "p1",
                    "person_name": "Mona",
                    "scoped": True,
                }
            ],
        }
    ],
    "citations": [],
    "uncertainty": None,
    "model": "reader",
    "reader_model": "reader",
    "embedding_model": None,
    "prompt_version": "assess-v1",
    "index_revision": None,
}

EXPECTED_ASSESSMENT = ArchitectureAssessment(
    knowledge_version="rel-7",
    facets=(
        AssessedFacet(
            "need",
            "Static IP for SMB fibre",
            "static IP",
            concepts=(AssessedConcept("cap:ip", "Static IP", "Net > IP"),),
        ),
    ),
    coverage=(AssessedCoverage("cap:ip", "Static IP", "Net > IP", ("c1",), ("bcrm",), True),),
    offering_id="offering:fiber",
    verdict="change_existing_offering",
    rule_verdict="change_existing_offering",
    verdict_reason="Business Fiber covers it.",
    proposal=AssessedProposal(
        "Add a quota.",
        "offering:fiber",
        components=(AssessedComponent("offering:fiber", "c1", "IP"),),
        new_values=("Quota",),
    ),
    systems=(
        AssessedSystem(
            "bcrm", "BCRM", "primary", "modify", ((AssessedPathStep("system", "bcrm", "BCRM"),),)
        ),
    ),
    gaps=(AssessedGap("staffing", "cap:ip", "Static IP", "No squad.", "bcrm"),),
    questions=(
        AssessedQuestion(
            "offering", "Which offering?", (AssessedOption("Business Fiber", "offering:fiber"),)
        ),
    ),
    owners=(
        AssessedOwners(
            "cap:ip",
            "bcrm",
            squads=(AssessedReference("sales", "Sales"),),
            seats=(AssessedSeat("sales", "lead", "p1", "Mona", True),),
        ),
    ),
    model="reader",
    reader_model="reader",
    prompt_version="assess-v1",
)


def test_an_assessment_is_asked_for_and_decoded_as_the_contract_describes() -> None:
    seen: list[httpx.Request] = []

    assessment = HttpArchitectureAssessment(_client(_answering(ASSESSMENT), seen)).assess(
        AssessmentQuery(("Static IP for SMB fibre.",), ("BCRM",), "rel-7", "REQ-7")
    )

    (request,) = seen
    _assert_in_contract(request)
    _assert_answer_in_contract(request, ASSESSMENT)
    assert (request.method, request.url.path) == ("POST", "/internal/architecture/assess")
    assert json.loads(request.content) == {
        "text": ["Static IP for SMB fibre."],
        "declared_systems": ["BCRM"],
        "release_id": "rel-7",
        # Its own decided verdict is never shown back to it (ontology plan Phase 5).
        "requirement_id": "REQ-7",
    }
    assert assessment == EXPECTED_ASSESSMENT


def test_the_precedents_an_assessment_weighed_are_allowed_and_not_needed() -> None:
    """Phase 5 adds the precedents and the reranker to the answer; requirement work reads
    neither yet, and an answer carrying them decodes to the same assessment."""
    seen: list[httpx.Request] = []
    later = {
        **json.loads(json.dumps(ASSESSMENT)),
        "reranker_model": "lexical-bm25-v1",
        "precedents": [
            {
                "precedent_id": "ANA-1",
                "requirement_id": "REQ-1",
                "release_id": "rel-7",
                "verdict": "new_plan",
                "decision": "overridden",
                "offering_id": "offering:fiber",
                "score": 0.71,
                "system_ids": ["bcrm"],
                "shared_concept_ids": ["cap:ip"],
            }
        ],
    }

    assessment = HttpArchitectureAssessment(_client(_answering(later), seen)).assess(
        AssessmentQuery(("Static IP for SMB fibre.",))
    )

    _assert_answer_in_contract(seen[0], later)
    assert assessment == EXPECTED_ASSESSMENT


def test_a_drafted_offering_is_decoded_and_kept_as_the_service_wrote_it() -> None:
    seen: list[httpx.Request] = []
    drafted = json.loads(json.dumps(ASSESSMENT))
    drafted["verdict"] = drafted["rule_verdict"] = "new_product_line"
    drafted["proposal"]["draft"] = DRAFTED_OFFERING

    assessment = HttpArchitectureAssessment(_client(_answering(drafted), seen)).assess(
        AssessmentQuery(("Cloud video surveillance for shops.",))
    )

    _assert_answer_in_contract(seen[0], drafted)
    assert assessment is not None and assessment.proposal is not None
    draft = assessment.proposal.draft
    assert draft is not None
    assert (draft.offering.name, draft.based_on) == (
        "Cloud video surveillance for shops",
        "offering:fiber",
    )
    assert [
        (part.name, [duty.system_id for duty in part.responsibilities])
        for part in draft.offering.components
    ] == [("Managed access point", ["ecm", "wfms"]), ("Cloud video surveillance", [])]
    assert [item.text for item in draft.offering.questions] == [
        "Which system will realise Cloud video surveillance?"
    ]
    assert draft.journey is not None and len(draft.journey.activities) == 2
    assert draft.document == DRAFTED_OFFERING


def test_a_role_kind_or_facet_added_later_is_read_as_written() -> None:
    """Additive contract values (AGENTS.md section 2.1) must not fail an analysis."""
    later = json.loads(json.dumps(ASSESSMENT))
    later["systems"][0]["role"] = "owner"
    later["systems"][0]["paths"][0][0]["kind"] = "interface"
    later["facets"][0]["kind"] = "interface"

    assessment = HttpArchitectureAssessment(_client(_answering(later))).assess(
        AssessmentQuery(("text",))
    )

    assert assessment is not None
    assert assessment.systems[0].role == "owner"
    assert assessment.systems[0].paths[0][0].kind == "interface"
    assert assessment.facets[0].kind == "interface"


def test_a_portal_without_the_assessment_offers_none() -> None:
    older = _client(_answering({"detail": "Not Found"}, status=404))

    assert HttpArchitectureAssessment(older).assess(AssessmentQuery(("text",))) is None
    assert not FakeArchitectureAssessment().is_connected()
    assert FakeArchitectureAssessment().assess(AssessmentQuery(("text",))) is None


def test_an_unusable_assessment_is_an_explicit_failure() -> None:
    with pytest.raises(ServiceUnavailableError):
        HttpArchitectureAssessment(_client(_answering({"verdict": "maybe"}))).assess(
            AssessmentQuery(("text",))
        )
