"""Secrets from files (production hardening PR 10): NAME, or the file NAME_FILE names."""

from __future__ import annotations

from pathlib import Path

import pytest

from smb_requirement_agent.infrastructure.config.options import ConfigurationError
from smb_requirement_agent.infrastructure.config.settings import (
    PersistenceSettings,
    Settings,
    _ProfileEnvironment,
)

SECRETS: tuple[tuple[str, str, dict[str, str]], ...] = (
    ("OPENAI_API_KEY", "openai_api_key", {"LLM_PROVIDER": "openai"}),
    ("OPENROUTER_API_KEY", "openrouter_api_key", {"LLM_PROVIDER": "openrouter"}),
    ("KNOWLEDGE_SERVICE_TOKEN", "knowledge_service_token", {}),
    (
        "REQUIREMENT_SERVICE_TOKEN",
        "requirement_service_token",
        {"KNOWLEDGE_API_BASE_URL": "http://knowledge"},
    ),
)


@pytest.mark.parametrize(("name", "field", "context"), SECRETS)
def test_a_secret_is_read_from_its_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, field: str, context: dict[str, str]
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    for key, value in context.items():
        monkeypatch.setenv(key, value)
    secret = tmp_path / "secret"
    secret.write_text("s" * 40 + "\n", encoding="utf-8")
    monkeypatch.setenv(f"{name}_FILE", str(secret))

    assert getattr(Settings.from_env(), field) == "s" * 40


def test_the_client_secret_is_read_from_its_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    secret = tmp_path / "secret"
    secret.write_text("client-secret", encoding="utf-8")
    monkeypatch.setenv("OIDC_ISSUER_URL", "https://identity.example.test")
    monkeypatch.setenv("REQUIREMENT_SERVICE_CLIENT_ID", "requirement-service")
    monkeypatch.setenv("REQUIREMENT_SERVICE_CLIENT_SECRET_FILE", str(secret))
    monkeypatch.setenv("KNOWLEDGE_API_BASE_URL", "http://knowledge")

    assert Settings.from_env().requirement_service_client_secret == "client-secret"


@pytest.mark.parametrize("problem", ["both", "missing", "empty"])
def test_an_ambiguous_missing_or_empty_secret_file_stops_the_boot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, problem: str
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    secret = tmp_path / "secret"
    if problem == "both":
        secret.write_text("sk-file", encoding="utf-8")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    elif problem == "empty":
        secret.write_text("  \n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY_FILE", str(secret))

    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        Settings.from_env()


def test_the_database_password_fills_a_url_that_has_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret = tmp_path / "password"
    secret.write_text("p@ss:word/1", encoding="utf-8")
    monkeypatch.setenv("PERSISTENCE_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://smb@db.example.test:5432/smb?sslmode=require")
    monkeypatch.setenv("DATABASE_PASSWORD_FILE", str(secret))

    assert PersistenceSettings.from_env().database_url == (
        "postgresql://smb:p%40ss%3Aword%2F1@db.example.test:5432/smb?sslmode=require"
    )

    monkeypatch.setenv("DATABASE_URL", "postgresql://smb:inline@db.example.test/smb")
    with pytest.raises(ConfigurationError, match="no password"):
        PersistenceSettings.from_env()


def test_a_model_profile_key_may_come_from_its_file(tmp_path: Path) -> None:
    secret = tmp_path / "key"
    secret.write_text("sk-profile", encoding="utf-8")
    environment = _ProfileEnvironment(
        {"PROFILE_KEY_FILE": str(secret), "SSL_CERT_FILE": "/nonexistent/cert.pem"}
    )

    assert environment.get("PROFILE_KEY", "") == "sk-profile"
    # Only names a profile asks for are read; an unrelated *_FILE is never touched.
    assert environment.get("UNSET_KEY", "") == ""
