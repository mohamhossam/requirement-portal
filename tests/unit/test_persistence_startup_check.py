from __future__ import annotations

from unittest.mock import MagicMock

import psycopg
import pytest

from smb_requirement_agent.infrastructure.config.options import PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import PersistenceSettings
from smb_requirement_agent.infrastructure.persistence import startup_check
from smb_requirement_agent.infrastructure.persistence.startup_check import (
    PersistenceTarget,
    check_persistence,
    classify_persistence,
)


def test_memory_persistence_needs_no_external_check(monkeypatch: pytest.MonkeyPatch) -> None:
    connect = MagicMock()
    monkeypatch.setattr(psycopg, "connect", connect)

    check_persistence(PersistenceSettings())

    connect.assert_not_called()


def test_postgres_readiness_uses_a_bounded_authenticated_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connect = MagicMock(return_value=connection)
    monkeypatch.setattr(psycopg, "connect", connect)
    settings = PersistenceSettings(
        provider=PersistenceProvider.POSTGRES,
        database_url="postgresql://user:secret@127.0.0.1:5432/app",
    )

    check_persistence(settings)

    connect.assert_called_once_with(
        settings.database_url,
        connect_timeout=3,
        options="-c statement_timeout=3000",
    )
    connection.execute.assert_called_once_with("SELECT 1")


def test_postgres_readiness_failure_has_actionable_message_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        psycopg,
        "connect",
        MagicMock(side_effect=psycopg.OperationalError("connection refused")),
    )
    settings = PersistenceSettings(
        provider=PersistenceProvider.POSTGRES,
        database_url="postgresql://user:secret@127.0.0.1:5432/app",
    )

    with pytest.raises(RuntimeError, match="PostgreSQL is not ready") as caught:
        check_persistence(settings)

    assert "secret" not in str(caught.value)
    assert "PERSISTENCE_PROVIDER=memory" in str(caught.value)


@pytest.mark.parametrize(
    ("database_url", "expected"),
    [
        ("postgresql://db.example.test/app", PersistenceTarget.EXTERNAL_POSTGRES),
        ("postgresql://localhost/app", PersistenceTarget.LOCAL_POSTGRES),
        ("postgresql://127.0.0.1:5432/app", PersistenceTarget.LOCAL_POSTGRES),
        ("postgresql://[::1]/app", PersistenceTarget.LOCAL_POSTGRES),
    ],
)
def test_persistence_target_classification(database_url: str, expected: PersistenceTarget) -> None:
    settings = PersistenceSettings(
        provider=PersistenceProvider.POSTGRES,
        database_url=database_url,
    )

    assert classify_persistence(settings) is expected


def test_quiet_probe_returns_failure_without_writing_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = PersistenceSettings(
        provider=PersistenceProvider.POSTGRES,
        database_url="postgresql://127.0.0.1:5432/app",
    )
    monkeypatch.setattr(PersistenceSettings, "from_env", lambda: settings)
    monkeypatch.setattr(
        psycopg,
        "connect",
        MagicMock(side_effect=psycopg.OperationalError("connection refused")),
    )

    result = startup_check.main(["--quiet"])

    assert result == 1
    assert capsys.readouterr().err == ""
