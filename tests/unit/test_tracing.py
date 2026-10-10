"""Optional tracing (ADR-0110): requests, job attempts and outbound calls, off by default.

The kernel tests the spans themselves; these test what the portal decides: which
requests are traced and how they are named, that a job attempt is one trace, and
that only the knowledge portal is sent the trace context.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import httpx
import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from smb_kernel.observability.metrics import Metrics
from smb_kernel.observability.tracing_setup import NO_TRACING, Tracing, configure_tracing
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.interfaces.api.composition import llm
from smb_requirement_agent.interfaces.api.composition import tracing as tracing_composition
from smb_requirement_agent.interfaces.api.composition.references import build_knowledge_service
from smb_requirement_agent.interfaces.api.composition.tracing import build_tracing, identity_client
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.jobs.application.ports.ai_jobs import (
    AiJobCommand,
    AiJobQueuePort,
    AiJobRecord,
)
from smb_requirement_agent.jobs.domain.entities import (
    AiJob,
    AiJobId,
    AiJobOperation,
    AiJobStatus,
)
from smb_requirement_agent.shared_kernel.actors import ActorId, ActorSnapshot
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.workflows.application.use_cases.ai_job_execution import ExecuteAiJob
from smb_requirement_agent.workflows.infrastructure.polling_worker import PollingAiJobWorker
from tests.conftest import FAKE_PROVIDER_SETTINGS

TRACED = replace(FAKE_PROVIDER_SETTINGS, tracing_endpoint="http://otel-collector:4318")
CALLER_TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)


@pytest.fixture
def exported(monkeypatch: pytest.MonkeyPatch) -> InMemorySpanExporter:
    """Spans the process would export, kept in memory instead of sent to a collector."""
    spans = InMemorySpanExporter()

    def in_memory(endpoint: str, **options: Any) -> Tracing:
        return configure_tracing(endpoint, **options, exporter=spans)

    monkeypatch.setattr(tracing_composition, "configure_tracing", in_memory)
    return spans


@pytest.fixture
def tracing(exported: InMemorySpanExporter) -> Iterator[Tracing]:
    with ExitStack() as resources:
        yield build_tracing(TRACED, resources)


def _flushed(tracing: Tracing, exported: InMemorySpanExporter) -> list[ReadableSpan]:
    provider = tracing.tracer_provider
    assert isinstance(provider, SdkTracerProvider)
    provider.force_flush()
    return list(exported.get_finished_spans())


def _recording(seen: list[httpx.Request]) -> Callable[..., httpx.BaseTransport]:
    def transport(**_options: Any) -> httpx.BaseTransport:
        def handle(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json={"has_published": True})

        return httpx.MockTransport(handle)

    return transport


def test_without_an_endpoint_nothing_is_traced() -> None:
    with ExitStack() as resources:
        assert build_tracing(FAKE_PROVIDER_SETTINGS, resources) is NO_TRACING
    container = build_container(FAKE_PROVIDER_SETTINGS)
    try:
        assert container.tracing is NO_TRACING
        with TestClient(create_app(lambda: container)) as client:
            assert client.get("/requirements").status_code == 200
    finally:
        container.close_resources()


def test_the_service_and_release_name_every_span(
    tracing: Tracing, exported: InMemorySpanExporter
) -> None:
    with tracing.span("work"):
        pass

    (span,) = _flushed(tracing, exported)
    assert span.resource.attributes["service.name"] == "requirement-portal"
    assert span.resource.attributes["service.version"]


def test_requests_are_traced_by_route_and_continue_the_callers_trace(
    exported: InMemorySpanExporter,
) -> None:
    container = build_container(TRACED)
    try:
        with TestClient(create_app(lambda: container)) as client:
            created = client.post(
                "/requirements", json={"title": "Fibre rollout", "description": "SMB sites"}
            ).json()["id"]
            read = client.get(
                f"/requirements/{created}",
                headers={
                    "traceparent": f"00-{CALLER_TRACE}-00f067aa0ba902b7-01",
                    "X-Request-ID": "req-42",
                },
            )
            searched = client.get("/requirements", params={"q": "private search text"})
            client.get("/health")
            client.get("/ready")
        assert (read.status_code, searched.status_code) == (200, 200)
        spans = _flushed(container.tracing, exported)
    finally:
        container.close_resources()

    servers = [span for span in spans if span.kind is SpanKind.SERVER]
    names = [span.name for span in servers]
    # Probes are not traced; every other request is one server span named by its route.
    assert names == [
        "POST /requirements",
        "GET /requirements/{requirement_id}",
        "GET /requirements",
    ]
    detail = servers[1]
    assert format(detail.context.trace_id, "032x") == CALLER_TRACE
    assert detail.attributes is not None
    assert detail.attributes["request.correlation_id"] == "req-42"
    assert detail.attributes["http.response.status_code"] == 200
    exported_text = "".join(span.to_json() for span in spans)
    # Identifiers in paths and search text in queries never leave the process.
    assert created not in exported_text
    assert "private search text" not in exported_text


def test_a_job_attempt_is_one_trace_named_by_its_operation(
    tracing: Tracing, exported: InMemorySpanExporter
) -> None:
    job = AiJob(
        AiJobId(f"job-{uuid.uuid4()}"),
        RequirementId("requirement-1"),
        AiJobOperation.ANALYSE_REQUIREMENT,
        AiJobStatus.QUEUED,
        ActorSnapshot(ActorId("owner"), "Owner"),
        NOW,
        NOW,
        "key",
        "fingerprint",
    ).claim(NOW)
    record = AiJobRecord(
        job,
        AiJobCommand({}),
        worker_id="worker",
        attempt_token="attempt-1",
        lease_until=NOW + timedelta(seconds=30),
    )
    finished = job.succeed((), NOW)

    class Queue:
        def __init__(self) -> None:
            self.records = [record]

        def claim_next(self, *_args: object, **_kwargs: object) -> AiJobRecord | None:
            return self.records.pop() if self.records else None

        def heartbeat(self, *_args: object) -> bool:
            return True

        def release(self, *_args: object) -> None:
            return None

        def fence_attempt(self, *_args: object) -> bool:
            return True

    class Executor:
        def __init__(self) -> None:
            self.done = False

        def execute(self, _record: AiJobRecord) -> AiJob:
            with tracing.span("inside the attempt"):
                self.done = True
            return finished

    executor = Executor()
    worker = PollingAiJobWorker(
        cast(AiJobQueuePort, Queue()),
        cast(ExecuteAiJob, executor),
        FixedClock(NOW),
        Metrics(),
        tracing,
        poll_interval_seconds=0.01,
        lease_seconds=30,
        heartbeat_seconds=5,
        shutdown_grace_seconds=1,
    )
    worker.start()
    try:
        deadline = time.monotonic() + 2
        while not executor.done and time.monotonic() < deadline:
            time.sleep(0.01)
    finally:
        worker.stop()

    spans = {span.name: span for span in _flushed(tracing, exported)}
    attempt = spans["ai_job analyse_requirement"]
    assert attempt.parent is None
    assert attempt.attributes is not None
    assert attempt.attributes["ai_job.id"] == job.id.value
    assert attempt.attributes["ai_job.operation"] == "analyse_requirement"
    inner = spans["inside the attempt"]
    assert inner.parent is not None and inner.parent.span_id == attempt.context.span_id


def test_only_the_knowledge_portal_is_sent_the_trace_context(
    monkeypatch: pytest.MonkeyPatch, tracing: Tracing, exported: InMemorySpanExporter
) -> None:
    seen: list[httpx.Request] = []
    monkeypatch.setattr(httpx, "HTTPTransport", _recording(seen))
    settings = replace(
        FAKE_PROVIDER_SETTINGS,
        knowledge_api_base_url="http://knowledge",
        requirement_service_token="r" * 40,
    )
    with ExitStack() as resources, tracing.span("request"):
        knowledge = build_knowledge_service(settings, resources, Metrics(), tracing)
        knowledge.references.has_published()
        with httpx.Client(
            transport=llm._metered(Metrics(), tracing, "local", lambda _t: None)
        ) as model:
            model.post("http://model.local/v1/chat/completions", json={})
        with identity_client(tracing) as issuer:
            issuer.get("https://issuer.example/.well-known/openid-configuration")

    to_portal, to_model, to_issuer = seen
    assert to_portal.url.host == "knowledge"
    assert "traceparent" in to_portal.headers
    assert "traceparent" not in to_model.headers
    assert "traceparent" not in to_issuer.headers
    peers = sorted(
        str((span.attributes or {})["peer.service"])
        for span in _flushed(tracing, exported)
        if span.kind is SpanKind.CLIENT
    )
    assert peers == ["identity", "knowledge", "local"]


def test_fastapi_never_configures_telemetry_itself() -> None:
    app = create_app(lambda: build_container(FAKE_PROVIDER_SETTINGS))
    telemetry = cast(dict[str, object], app._telemetry)  # noqa: SLF001 - pins the opt-out
    assert telemetry["auto_configure"] is False
    assert telemetry["tracing"] is False
    assert telemetry["logs"] is False
