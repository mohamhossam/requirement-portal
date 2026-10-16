"""Interactive API documentation is a development convenience, refused in production."""

from __future__ import annotations

from fastapi.testclient import TestClient

from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from tests.conftest import FAKE_PROVIDER_SETTINGS

DOCUMENTATION_PATHS = ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc")


def test_documentation_is_served_outside_production() -> None:
    container = build_container(FAKE_PROVIDER_SETTINGS)
    with TestClient(create_app(lambda: container)) as client:
        assert client.get("/openapi.json").status_code == 200
        assert client.get("/docs").status_code == 200


def test_documentation_answers_404_in_production() -> None:
    # The app itself refuses the documentation surface, so the promise holds even
    # when the container is reached directly, without the bundled edge. Settings
    # validation refuses production with fakes, so the environment is forced onto
    # this test's own frozen settings instance: the middleware reads only this field.
    settings = Settings(llm_provider=LLMProvider.FAKE, library_scan_mode="offline")
    object.__setattr__(settings, "app_environment", "production")
    container = build_container(settings)
    with TestClient(create_app(lambda: container)) as client:
        for path in DOCUMENTATION_PATHS:
            assert client.get(path).status_code == 404, path
        assert client.get("/health").status_code == 200
