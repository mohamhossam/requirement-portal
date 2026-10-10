"""A traced request's SQL is part of its trace, with statements but never values (ADR-0110)."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from typing import Any
from urllib.parse import quote

import psycopg
import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from smb_kernel.observability.tracing_setup import Tracing, configure_tracing

from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.interfaces.api.composition import tracing as tracing_composition
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
TITLE = "Confidential fibre rollout"


@pytest.fixture
def exported(monkeypatch: pytest.MonkeyPatch) -> InMemorySpanExporter:
    spans = InMemorySpanExporter()

    def in_memory(endpoint: str, **options: Any) -> Tracing:
        return configure_tracing(endpoint, **options, exporter=spans)

    monkeypatch.setattr(tracing_composition, "configure_tracing", in_memory)
    return spans


@pytest.fixture
def container(exported: InMemorySpanExporter) -> Iterator[Container]:
    assert DATABASE_URL is not None
    schema = f"tracing_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    url = f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    run_migrations(url)
    built = build_container(
        Settings(
            llm_provider=LLMProvider.FAKE,
            persistence_provider=PersistenceProvider.POSTGRES,
            database_url=url,
            tracing_endpoint="http://otel-collector:4318",
        )
    )
    try:
        yield built
    finally:
        built.close_resources()
        with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
            connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def test_a_requests_statements_are_its_children(
    container: Container, exported: InMemorySpanExporter
) -> None:
    with TestClient(create_app(lambda: container)) as client:
        created = client.post("/requirements", json={"title": TITLE, "description": "SMB sites"})
    assert created.status_code == 201, created.text
    provider = container.tracing.tracer_provider
    assert isinstance(provider, SdkTracerProvider)
    provider.force_flush()
    spans = exported.get_finished_spans()

    (request,) = [span for span in spans if span.name == "POST /requirements"]
    statements = [
        span
        for span in spans
        if span.kind is SpanKind.CLIENT
        and span.parent is not None
        and span.context.trace_id == request.context.trace_id
    ]
    assert statements, [span.name for span in spans]
    assert any(
        "INSERT" in str((span.attributes or {}).get("db.statement", "")) for span in statements
    )
    exported_text = "".join(span.to_json() for span in spans)
    assert TITLE not in exported_text
