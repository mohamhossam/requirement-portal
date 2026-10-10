"""The API server entrypoint configures logging, then serves without uvicorn's own logs."""

from __future__ import annotations

import pytest

from smb_requirement_agent.infrastructure.config.options import (
    ConfigurationError,
    LLMProvider,
    LogFormat,
)
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api import serve


def test_configures_logging_before_serving_the_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, object]] = []
    settings = Settings(
        llm_provider=LLMProvider.FAKE, log_level="WARNING", log_format=LogFormat.JSON
    )
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(
        serve, "configure_logging", lambda level, fmt: events.append(("logging", (level, fmt)))
    )
    monkeypatch.setattr("uvicorn.run", lambda app, **options: events.append(("run", options)))

    assert serve.main(["--host", "0.0.0.0", "--port", "9000"]) == 0  # noqa: S104 - asserts the value passed through

    assert events[0] == ("logging", ("WARNING", LogFormat.JSON))
    name, options = events[1]
    assert name == "run"
    assert isinstance(options, dict)
    # The application logs each request itself; uvicorn must not add a second
    # access log or replace the configured handlers.
    assert options["log_config"] is None
    assert options["access_log"] is False
    assert (options["host"], options["port"]) == ("0.0.0.0", 9000)  # noqa: S104 - asserts the value passed through


def test_an_invalid_configuration_exits_before_serving(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def invalid(cls: type[Settings]) -> Settings:
        raise ConfigurationError("LOG_FORMAT must be text or json.")

    monkeypatch.setattr(Settings, "from_env", classmethod(invalid))
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: pytest.fail("served"))

    assert serve.main([]) == 2
    assert "LOG_FORMAT" in capsys.readouterr().err
