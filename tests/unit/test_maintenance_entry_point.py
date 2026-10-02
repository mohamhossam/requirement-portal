"""The offline maintenance command: PostgreSQL only, one rebuild, a readable result.

`build_projection_rebuild` itself runs against PostgreSQL in
`tests/integration/test_source_lineage_postgres.py`; this covers the command
around it, which the first install depends on before `/ready` passes.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

import pytest

from smb_requirement_agent.infrastructure.config.options import ConfigurationError
from smb_requirement_agent.interfaces import maintenance


@pytest.fixture(autouse=True)
def _no_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["maintenance"])


def test_memory_persistence_is_refused_without_touching_any_store(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PERSISTENCE_PROVIDER", "memory")
    monkeypatch.setattr(maintenance, "build_projection_rebuild", _unexpected)

    with pytest.raises(SystemExit) as exited:
        maintenance.main()

    assert exited.value.code == 2
    assert "requires PostgreSQL persistence and DATABASE_URL" in capsys.readouterr().err


def test_postgres_without_a_database_url_is_refused_by_the_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PERSISTENCE_PROVIDER", "postgres")
    # Empty, not unset: settings load `.env`, which never overrides a set variable.
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr(maintenance, "build_projection_rebuild", _unexpected)

    with pytest.raises(ConfigurationError, match="requires DATABASE_URL"):
        maintenance.main()


def test_postgres_rebuilds_once_and_reports_the_count(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PERSISTENCE_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://maintenance@db/app")
    calls: list[str] = []

    def build(database_url: str) -> Callable[[], int]:
        calls.append(database_url)
        return lambda: 7

    monkeypatch.setattr(maintenance, "build_projection_rebuild", build)

    maintenance.main()

    assert calls == ["postgresql://maintenance@db/app"]
    assert capsys.readouterr().out.strip() == (
        "Rebuilt activity and worklist projections for 7 Requirements."
    )


def test_unknown_arguments_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["maintenance", "--force"])
    monkeypatch.setattr(maintenance, "build_projection_rebuild", _unexpected)

    with pytest.raises(SystemExit) as exited:
        maintenance.main()

    assert exited.value.code == 2


def _unexpected(database_url: str) -> Callable[[], int]:
    raise AssertionError("The rebuild must not be built for a refused run.")
