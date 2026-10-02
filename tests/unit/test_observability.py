"""Operational logging, correlation and metrics."""

from __future__ import annotations

import json
import logging
import socket
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import cast

import httpx
import httpx2
import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.ports.ai_jobs import (
    AiJobCommand,
    AiJobQueuePort,
    AiJobRecord,
)
from smb_requirement_agent.application.use_cases.ai_job_execution import ExecuteAiJob
from smb_requirement_agent.domain.jobs.entities import AiJob
from smb_requirement_agent.infrastructure.config.options import LogFormat
from smb_requirement_agent.infrastructure.jobs.polling_worker import PollingAiJobWorker
from smb_requirement_agent.infrastructure.observability.correlation import (
    correlation_scope,
    current_correlation_id,
)
from smb_requirement_agent.infrastructure.observability.logging import (
    JsonLogFormatter,
    configure_logging,
)
from smb_requirement_agent.infrastructure.observability.metrics import (
    MeteredTransport,
    MeteredTransport2,
    Metrics,
    provider_operation,
    provider_usage,
)
from smb_requirement_agent.infrastructure.time.fixed_clock import FixedClock
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.interfaces.runtime import start_metrics
from tests.conftest import FAKE_PROVIDER_SETTINGS
from tests.unit.test_ai_jobs import NOW, _job
from tests.unit.test_polling_worker import RecordingQueue


def _sample(metrics: Metrics, name: str, labels: dict[str, str]) -> float:
    value = metrics.registry.get_sample_value(name, labels)
    return 0.0 if value is None else value


class TestJsonLogs:
    def _format(self, record: logging.LogRecord) -> dict[str, object]:
        payload: dict[str, object] = json.loads(JsonLogFormatter().format(record))
        return payload

    def test_a_record_is_one_json_object_with_the_correlation_id_and_extras(self) -> None:
        record = logging.LogRecord("smb.test", logging.INFO, __file__, 1, "done %s", ("x",), None)
        record.duration_ms = 12.5

        with correlation_scope("request-1"):
            payload = self._format(record)

        assert payload["message"] == "done x"
        assert payload["level"] == "INFO"
        assert payload["logger"] == "smb.test"
        assert payload["correlation_id"] == "request-1"
        assert payload["duration_ms"] == 12.5
        assert "args" not in payload

    def test_exceptions_are_included(self) -> None:
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            record = logging.LogRecord(
                "smb.test", logging.ERROR, __file__, 1, "failed", None, sys.exc_info()
            )

        assert "RuntimeError: boom" in str(self._format(record)["exception"])

    def test_the_correlation_scope_ends_with_its_block(self) -> None:
        with correlation_scope("outer"):
            with correlation_scope("inner"):
                assert current_correlation_id() == "inner"
            assert current_correlation_id() == "outer"
        assert current_correlation_id() is None


def test_configuring_twice_keeps_one_operational_handler() -> None:
    root = logging.getLogger()
    before = list(root.handlers)
    level = root.level
    try:
        configure_logging("INFO", LogFormat.JSON)
        configure_logging("WARNING", LogFormat.TEXT)

        added = [handler for handler in root.handlers if handler not in before]
        assert len(added) == 1
        assert root.level == logging.WARNING
    finally:
        for handler in [h for h in root.handlers if h not in before]:
            root.removeHandler(handler)
        root.setLevel(level)


class TestRequests:
    def test_requests_are_counted_by_route_template_and_logged_with_their_correlation(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        container = build_container(FAKE_PROVIDER_SETTINGS)
        with TestClient(create_app(lambda: container)) as client:
            created = client.post("/requirements", json={"title": "T", "description": "D"})
            requirement_id = created.json()["id"]
            with caplog.at_level(logging.INFO, logger="smb_requirement_agent.http"):
                response = client.get(
                    f"/requirements/{requirement_id}", headers={"X-Request-ID": "trace-42"}
                )

        assert response.headers["X-Request-ID"] == "trace-42"
        labels = {"method": "GET", "route": "/requirements/{requirement_id}", "status": "200"}
        assert _sample(container.metrics, "smb_http_requests_total", labels) == 1
        [line] = [r for r in caplog.records if r.name == "smb_requirement_agent.http"]
        assert line.__dict__["route"] == "/requirements/{requirement_id}"
        assert requirement_id not in line.getMessage()

    def test_the_request_correlation_reaches_synchronous_endpoints(self) -> None:
        seen: list[str | None] = []
        container = build_container(FAKE_PROVIDER_SETTINGS)
        application = create_app(lambda: container)

        @application.get("/probe-correlation")
        def probe() -> dict[str, str]:
            seen.append(current_correlation_id())
            return {}

        with TestClient(application) as client:
            client.get("/probe-correlation", headers={"X-Request-ID": "sync-7"})

        assert seen == ["sync-7"]

    def test_unknown_paths_share_one_label(self) -> None:
        container = build_container(FAKE_PROVIDER_SETTINGS)
        with TestClient(create_app(lambda: container)) as client:
            client.get("/no/such/path/123")

        labels = {"method": "GET", "route": "unmatched", "status": "404"}
        assert _sample(container.metrics, "smb_http_requests_total", labels) == 1


class TestProviderRequests:
    @pytest.mark.parametrize(
        ("path", "operation"),
        [
            ("/v1/chat/completions", "generation"),
            ("/api/v1/embeddings", "embeddings"),
            ("/v1/responses", "generation"),
            ("/v1/models/abc-123", "other"),
        ],
    )
    def test_operations_are_a_bounded_label(self, path: str, operation: str) -> None:
        assert provider_operation(path) == operation

    def test_responses_and_failures_are_counted(self) -> None:
        metrics = Metrics()

        def reply(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("embeddings"):
                raise httpx.ConnectError("refused")
            return httpx.Response(429)

        client = httpx.Client(
            transport=MeteredTransport(metrics, "local", httpx.MockTransport(reply))
        )
        client.post("http://model.test/v1/chat/completions", json={})
        with pytest.raises(httpx.ConnectError):
            client.post("http://model.test/v1/embeddings", json={})

        generation = {"provider": "local", "operation": "generation", "outcome": "4xx"}
        failure = {"provider": "local", "operation": "embeddings", "outcome": "error"}
        assert _sample(metrics, "smb_provider_requests_total", generation) == 1
        assert _sample(metrics, "smb_provider_requests_total", failure) == 1


class FinishingExecutor:
    def __init__(self, result: AiJob) -> None:
        self.result = result
        self.done = threading.Event()

    def execute(self, record: AiJobRecord) -> AiJob:
        del record
        self.done.set()
        return self.result


def test_the_worker_records_each_job_attempt_by_operation_and_status() -> None:
    running = _job().claim(NOW)
    record = AiJobRecord(
        running,
        command=AiJobCommand({}),
        worker_id="worker",
        attempt_token="attempt-1",
        lease_until=NOW + timedelta(seconds=30),
    )
    finished = running.succeed((), NOW)
    executor = FinishingExecutor(finished)
    metrics = Metrics()
    worker = PollingAiJobWorker(
        cast(AiJobQueuePort, RecordingQueue(record)),
        cast(ExecuteAiJob, executor),
        FixedClock(NOW),
        metrics,
        poll_interval_seconds=0.01,
        lease_seconds=30,
        heartbeat_seconds=5,
        shutdown_grace_seconds=1,
    )
    worker.start()
    assert executor.done.wait(timeout=2)
    worker.stop()

    labels = {"operation": running.operation.value, "status": finished.status.value}
    assert _sample(metrics, "smb_ai_jobs_total", labels) == 1


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def test_the_exporter_serves_this_container_metrics_and_stops() -> None:
    container = build_container(replace(FAKE_PROVIDER_SETTINGS, metrics_port=_free_port()))
    container.metrics.record_http("GET", "/health", 200, 0.01)
    port = container.settings.metrics_port
    stop = start_metrics(container)
    try:
        body = httpx.get(f"http://127.0.0.1:{port}/metrics", timeout=5).text
    finally:
        stop()
        container.close_resources()

    assert 'smb_http_requests_total{method="GET",route="/health",status="200"} 1.0' in body
    # Refused on Linux; Windows may instead time out against the closed port.
    with pytest.raises(httpx.TransportError):
        httpx.get(f"http://127.0.0.1:{port}/metrics", timeout=1)


def test_without_a_port_no_exporter_is_started() -> None:
    container = build_container(FAKE_PROVIDER_SETTINGS)
    try:
        stop = start_metrics(container)
        stop()
    finally:
        container.close_resources()

    assert container.settings.metrics_port is None


class TestProviderTokens:
    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            (
                {"model": "gpt-x", "usage": {"prompt_tokens": 12, "completion_tokens": 30}},
                ("gpt-x", {"input": 12, "output": 30}),
            ),
            ({"model": "embed-1", "usage": {"prompt_tokens": 7}}, ("embed-1", {"input": 7})),
            (
                {"model": "r-1", "usage": {"input_tokens": 3, "output_tokens": 4}},
                ("r-1", {"input": 3, "output": 4}),
            ),
            ({"usage": {"prompt_tokens": 1}}, ("unknown", {"input": 1})),
            ({"model": "m", "usage": {"prompt_tokens": True, "completion_tokens": -2}}, None),
            ({"model": "m"}, None),
            (["not", "an", "object"], None),
        ],
    )
    def test_usage_is_read_from_the_provider_response(
        self, payload: object, expected: tuple[str, dict[str, int]] | None
    ) -> None:
        assert provider_usage(json.dumps(payload).encode()) == expected

    def test_a_body_that_is_not_json_reports_no_usage(self) -> None:
        assert provider_usage(b"<html>gateway error</html>") is None

    def test_tokens_are_counted_and_the_client_still_reads_the_body(self) -> None:
        body = {"model": "local-q", "usage": {"prompt_tokens": 5, "completion_tokens": 9}}
        with _json_server(body) as url:
            metrics = Metrics()
            client = httpx.Client(
                transport=MeteredTransport(metrics, "local", httpx.HTTPTransport())
            )
            reply = client.post(f"{url}/v1/chat/completions", json={})
            client2 = httpx2.Client(
                transport=MeteredTransport2(metrics, "openai", httpx2.HTTPTransport())
            )
            reply2 = client2.post(f"{url}/v1/chat/completions", json={})

        # The transport read the body; the caller still gets all of it.
        assert reply.json() == body
        assert reply2.json() == body
        for provider in ("local", "openai"):
            input_labels = {"provider": provider, "model": "local-q", "direction": "input"}
            output_labels = {"provider": provider, "model": "local-q", "direction": "output"}
            assert _sample(metrics, "smb_provider_tokens_total", input_labels) == 5
            assert _sample(metrics, "smb_provider_tokens_total", output_labels) == 9

    def test_failed_requests_count_no_tokens(self) -> None:
        metrics = Metrics()
        body = json.dumps({"model": "m", "usage": {"prompt_tokens": 50}}).encode()
        client = httpx.Client(
            transport=MeteredTransport(
                metrics, "local", httpx.MockTransport(lambda _: httpx.Response(429, content=body))
            )
        )

        client.post("http://model.test/v1/chat/completions", json={})

        labels = {"provider": "local", "model": "m", "direction": "input"}
        assert _sample(metrics, "smb_provider_tokens_total", labels) == 0


@contextmanager
def _json_server(payload: object) -> Iterator[str]:
    """A real HTTP server, so the transport reads a genuine network stream."""
    encoded = json.dumps(payload).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
