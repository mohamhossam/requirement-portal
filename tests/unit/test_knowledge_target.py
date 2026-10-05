"""The launchers' banner names the knowledge service exactly as the API decides it (ADR-0099)."""

from __future__ import annotations

import pytest

from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.knowledge_target import OFFLINE, describe

URL = "http://127.0.0.1:8100"
TOKEN = "requirement-service-token-for-tests-000000"


@pytest.fixture(autouse=True)
def _fake_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    # Set, even empty, so a developer's .env cannot fill them in.
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("KNOWLEDGE_API_BASE_URL", "")
    monkeypatch.setenv("REQUIREMENT_SERVICE_TOKEN", "")


def test_with_neither_setting_offline_stand_ins_answer() -> None:
    assert Settings.from_env().knowledge_service_url is None
    assert describe() == OFFLINE


def test_with_both_settings_the_knowledge_service_is_called_and_the_token_never_shown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KNOWLEDGE_API_BASE_URL", URL)
    monkeypatch.setenv("REQUIREMENT_SERVICE_TOKEN", TOKEN)

    assert Settings.from_env().knowledge_service_url == URL
    assert describe() == URL
    assert TOKEN not in describe()


def test_a_configuration_the_api_would_refuse_is_reported_without_failing_the_launch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KNOWLEDGE_API_BASE_URL", URL)

    assert describe().startswith("unknown")
