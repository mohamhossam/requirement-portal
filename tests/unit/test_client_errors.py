"""Browsers report their own failures (production hardening PR 12)."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from tests.conftest import FAKE_PROVIDER_SETTINGS


@pytest.fixture
def reporting() -> tuple[TestClient, Container]:
    container = build_container(FAKE_PROVIDER_SETTINGS)
    return TestClient(create_app(lambda: container)), container


def test_a_report_needs_no_sign_in_and_is_counted_by_kind(
    reporting: tuple[TestClient, Container], caplog: pytest.LogCaptureFixture
) -> None:
    client, container = reporting
    with client, caplog.at_level(logging.WARNING, logger="smb_requirement_agent.client_errors"):
        assert client.post("/client-errors", json={"kind": "render"}).status_code == 204
        assert client.post("/client-errors", json={"kind": "render"}).status_code == 204
        assert client.post("/client-errors", json={"kind": "chunk_load"}).status_code == 204

    registry = container.metrics.registry
    assert registry.get_sample_value("smb_client_errors_total", {"kind": "render"}) == 2
    assert registry.get_sample_value("smb_client_errors_total", {"kind": "chunk_load"}) == 1
    assert [record.getMessage() for record in caplog.records] == [
        "A browser reported a failure: render",
        "A browser reported a failure: render",
        "A browser reported a failure: chunk_load",
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "anything"},
        {},
        # A message or stack could carry what the person was working on.
        {"kind": "render", "message": "Cannot read properties of undefined"},
        {"kind": "render", "stack": "at RequirementPage (index.js:1:2)"},
    ],
)
def test_a_report_names_a_known_kind_and_nothing_else(
    reporting: tuple[TestClient, Container], body: dict[str, str]
) -> None:
    client, container = reporting
    with client:
        refused = client.post("/client-errors", json=body)

    assert refused.status_code == 422
    assert refused.json()["code"] == "validation_error"
    registry = container.metrics.registry
    assert registry.get_sample_value("smb_client_errors_total", {"kind": "anything"}) is None
