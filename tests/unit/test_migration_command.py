from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.infrastructure.config.options import PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import PersistenceSettings
from smb_requirement_agent.infrastructure.persistence import migrate


def test_migration_command_applies_postgres_schema(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = PersistenceSettings(
        provider=PersistenceProvider.POSTGRES,
        database_url="postgresql://database.example.test/app",
    )
    run_migrations = MagicMock()
    monkeypatch.setattr(PersistenceSettings, "from_env", lambda: settings)
    monkeypatch.setattr(migrate, "run_migrations", run_migrations)

    result = migrate.main()

    assert result == 0
    run_migrations.assert_called_once_with(settings.database_url)
    assert "schema is current" in capsys.readouterr().out


def test_migration_command_is_a_no_op_in_memory_mode(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        PersistenceSettings,
        "from_env",
        lambda: PersistenceSettings(provider=PersistenceProvider.MEMORY),
    )
    run_migrations = MagicMock()
    monkeypatch.setattr(migrate, "run_migrations", run_migrations)

    result = migrate.main()

    assert result == 0
    run_migrations.assert_not_called()
    assert "memory mode" in capsys.readouterr().out


def test_migration_command_reports_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = PersistenceSettings(
        provider=PersistenceProvider.POSTGRES,
        database_url="postgresql://database.example.test/app",
    )
    monkeypatch.setattr(PersistenceSettings, "from_env", lambda: settings)
    monkeypatch.setattr(
        migrate,
        "run_migrations",
        MagicMock(side_effect=PersistenceError("PostgreSQL migration failed")),
    )

    result = migrate.main()

    assert result == 1
    assert "PostgreSQL migration failed" in capsys.readouterr().err
