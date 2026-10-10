import inspect
import re
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from smb_requirement_agent.interfaces.api import main
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import app
from smb_requirement_agent.interfaces.release import APPLICATION_VERSION
from tests.conftest import FAKE_PROVIDER_SETTINGS

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": APPLICATION_VERSION}


def test_the_api_reports_the_version_the_package_declares() -> None:
    declared = re.search(r'^version = "([^"]+)"', PYPROJECT.read_text(encoding="utf-8"), re.M)

    assert declared is not None
    assert APPLICATION_VERSION == declared.group(1)
    assert app.version == declared.group(1)


def test_readiness_answers_in_time_when_the_database_check_hangs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stuck check reports the database unavailable instead of stalling the probe."""
    released = threading.Event()
    container = replace(
        build_container(FAKE_PROVIDER_SETTINGS),
        readiness_check=lambda: released.wait(5),
        background_workers={},
    )
    monkeypatch.setattr(main, "READINESS_TIMEOUT_SECONDS", 0.2)
    try:
        with TestClient(main.create_app(lambda: container)) as client:
            started = time.monotonic()
            response = client.get("/ready")
            elapsed = time.monotonic() - started
    finally:
        released.set()

    assert response.status_code == 503
    assert response.json()["checks"]["persistence"] is False
    assert elapsed < 2


def test_readiness_runs_off_the_request_thread_pool() -> None:
    """Both probes are coroutines, so a pool full of requests cannot queue them."""
    routes = {route.path: route for route in main.app.routes if isinstance(route, APIRoute)}

    assert inspect.iscoroutinefunction(routes["/health"].endpoint)
    assert inspect.iscoroutinefunction(routes["/ready"].endpoint)
