"""Deployment preflight refuses public traffic without real identity.

It is the last check before a workspace opens to the public, so its exit
codes are what automation acts on: 0 to proceed, 2 to stop.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from smb_requirement_agent.infrastructure.config.options import (
    ConfigurationError,
    IdentityProvider,
    LLMProvider,
)
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces import deployment_preflight
from tests.conftest import FAKE_PROVIDER_SETTINGS


def test_fake_identity_is_refused_for_public_traffic() -> None:
    with pytest.raises(ConfigurationError, match="IDENTITY_PROVIDER=oidc"):
        deployment_preflight.validate_public_deployment(FAKE_PROVIDER_SETTINGS)


def test_the_command_exits_2_with_the_reason(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(Settings, "from_env", staticmethod(lambda: FAKE_PROVIDER_SETTINGS))

    assert deployment_preflight.main() == 2
    assert "IDENTITY_PROVIDER=oidc" in capsys.readouterr().err


PUBLIC = replace(
    FAKE_PROVIDER_SETTINGS,
    identity_provider=IdentityProvider.OIDC,
    oidc_issuer_url="https://identity.example/tenant",
    oidc_audience="api://smb",
    oidc_client_id="browser",
    llm_provider=LLMProvider.OPENAI,
    openai_api_key="test-only",
)


def test_the_fake_model_is_refused_for_public_traffic() -> None:
    with pytest.raises(ConfigurationError, match="LLM_PROVIDER=fake"):
        deployment_preflight.validate_public_deployment(
            replace(PUBLIC, llm_provider=LLMProvider.FAKE)
        )


def test_the_debug_trace_is_refused_for_public_traffic() -> None:
    with pytest.raises(ConfigurationError, match="DEBUG_TRACE_ENABLED"):
        deployment_preflight.validate_public_deployment(replace(PUBLIC, debug_trace_enabled=True))


def test_the_command_exits_0_for_oidc_and_a_real_model(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(Settings, "from_env", staticmethod(lambda: PUBLIC))

    assert deployment_preflight.main() == 0
    assert "Verify /ready" in capsys.readouterr().out
