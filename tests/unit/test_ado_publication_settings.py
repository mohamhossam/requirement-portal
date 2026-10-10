"""Azure DevOps publication settings and the publisher the container chooses (Slice 12)."""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path

import pytest

from smb_requirement_agent.governance.infrastructure.publication.azure_devops import (
    AzureDevOpsWorkItemPublisher,
)
from smb_requirement_agent.governance.infrastructure.publication.fake import FakeBacklogPublisher
from smb_requirement_agent.governance.infrastructure.publication.unavailable import (
    UnavailableBacklogPublisher,
)
from smb_requirement_agent.infrastructure.config.options import AdoPublisher, ConfigurationError
from smb_requirement_agent.infrastructure.config.settings import (
    AdoPublicationSettings,
    Settings,
    parse_squad_area_paths,
)
from smb_requirement_agent.interfaces.api.composition.governance import build_backlog_publisher

ADO_VARIABLES = (
    "ADO_PUBLISHER",
    "ADO_ORGANIZATION_URL",
    "ADO_PROJECT",
    "ADO_PERSONAL_ACCESS_TOKEN",
    "ADO_PERSONAL_ACCESS_TOKEN_FILE",
    "ADO_AREA_PATH",
    "ADO_ITERATION_PATH",
    "ADO_SQUAD_AREA_PATHS",
    "ADO_TAGS",
    "ADO_TIMEOUT_SECONDS",
    "ADO_STORY_TYPE",
)


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    for name in ADO_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_publication_is_off_by_default() -> None:
    settings = Settings.from_env().ado_publication

    assert settings.publisher is AdoPublisher.NONE
    with ExitStack() as resources:
        assert isinstance(build_backlog_publisher(settings, resources), UnavailableBacklogPublisher)


def test_azure_devops_settings_are_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    token = tmp_path / "ado-pat"
    token.write_text("secret-pat\n", encoding="utf-8")
    monkeypatch.setenv("ADO_PUBLISHER", "azure_devops")
    monkeypatch.setenv("ADO_ORGANIZATION_URL", "https://dev.azure.com/contoso/")
    monkeypatch.setenv("ADO_PROJECT", "SMB")
    monkeypatch.setenv("ADO_PERSONAL_ACCESS_TOKEN_FILE", str(token))
    monkeypatch.setenv("ADO_ITERATION_PATH", "SMB\\PI 7")
    monkeypatch.setenv("ADO_STORY_TYPE", "Product Backlog Item")
    monkeypatch.setenv("ADO_TAGS", "smb; portal ;")
    monkeypatch.setenv("ADO_SQUAD_AREA_PATHS", "billing=SMB\\Billing; network=SMB\\Network")
    monkeypatch.setenv("ADO_TIMEOUT_SECONDS", "12")

    settings = Settings.from_env().ado_publication

    assert settings.organization_url == "https://dev.azure.com/contoso"
    assert settings.personal_access_token == "secret-pat"
    assert "secret-pat" not in repr(settings)
    assert settings.default_area_path == "SMB"
    assert settings.story_type == "Product Backlog Item"
    assert settings.tags == ("smb", "portal")
    assert settings.squad_area_paths == (("billing", "SMB\\Billing"), ("network", "SMB\\Network"))
    assert settings.timeout_seconds == 12.0
    with ExitStack() as resources:
        publisher = build_backlog_publisher(settings, resources)
        assert isinstance(publisher, AzureDevOpsWorkItemPublisher)
        assert publisher.target().location_for("network") == "SMB\\Network"


def test_the_fake_publisher_needs_no_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADO_PUBLISHER", "fake")

    settings = Settings.from_env().ado_publication

    with ExitStack() as resources:
        assert isinstance(build_backlog_publisher(settings, resources), FakeBacklogPublisher)


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"ADO_PUBLISHER": "jira"}, "Unsupported ADO_PUBLISHER 'jira'"),
        (
            {"ADO_PUBLISHER": "azure_devops"},
            "requires ADO_ORGANIZATION_URL, ADO_PROJECT, ADO_PERSONAL_ACCESS_TOKEN",
        ),
        (
            {
                "ADO_PUBLISHER": "azure_devops",
                "ADO_ORGANIZATION_URL": "dev.azure.com/contoso",
                "ADO_PROJECT": "SMB",
                "ADO_PERSONAL_ACCESS_TOKEN": "pat",
            },
            "ADO_ORGANIZATION_URL must be an http",
        ),
        (
            {
                "ADO_PUBLISHER": "azure_devops",
                "ADO_ORGANIZATION_URL": "https://dev.azure.com/contoso",
                "ADO_PROJECT": "SMB",
                "ADO_PERSONAL_ACCESS_TOKEN": "pat",
                "ADO_TIMEOUT_SECONDS": "0",
            },
            "ADO_TIMEOUT_SECONDS must be a positive number",
        ),
        ({"ADO_TIMEOUT_SECONDS": "soon"}, "ADO_TIMEOUT_SECONDS must be a number"),
        ({"ADO_SQUAD_AREA_PATHS": "billing"}, "ADO_SQUAD_AREA_PATHS entries must read"),
    ],
)
def test_incomplete_or_invalid_settings_fail_the_boot(
    monkeypatch: pytest.MonkeyPatch, environment: dict[str, str], message: str
) -> None:
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(ConfigurationError, match=message):
        Settings.from_env()


def test_a_squad_named_twice_is_refused() -> None:
    with pytest.raises(ConfigurationError, match="names squad 'billing' twice"):
        parse_squad_area_paths("billing=A;billing=B")
    assert parse_squad_area_paths(" ; ") == ()


def test_an_empty_type_name_is_refused() -> None:
    with pytest.raises(ConfigurationError, match="ADO_EPIC_TYPE must not be empty"):
        AdoPublicationSettings(
            publisher=AdoPublisher.AZURE_DEVOPS,
            organization_url="https://dev.azure.com/contoso",
            project="SMB",
            personal_access_token="pat",
            epic_type="",
        )
