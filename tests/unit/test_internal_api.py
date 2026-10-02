"""Requirement work's internal API for the knowledge service (ADR-0099)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from smb_kernel.http.service_auth import CALLER_SCOPE_KEY

from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirementInput
from smb_requirement_agent.application.use_cases.document_library import LibraryView
from smb_requirement_agent.infrastructure.config.options import ConfigurationError
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.interfaces.api.dependencies import require_service_caller
from smb_requirement_agent.interfaces.api.main import create_app
from tests.unit import test_reference_grounding

grounded = test_reference_grounding.grounded
TOKEN = "k" * 40
SERVICE = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def internal(grounded: tuple[Container, LibraryView]) -> Iterator[tuple[TestClient, LibraryView]]:
    container, document = grounded
    owner = FAKE_ACTORS[0]
    requirement = container.create_requirement.execute(
        CreateRequirementInput("Cites the policy", "XGPON coverage for bundles."), owner
    )
    container.analyze_requirement.execute(owner, requirement.id)
    serving = replace(
        container, settings=replace(container.settings, knowledge_service_token=TOKEN)
    )
    with TestClient(create_app(lambda: serving)) as client:
        yield client, document


def test_without_a_token_the_internal_api_is_not_served(
    grounded: tuple[Container, LibraryView],
) -> None:
    container, _ = grounded
    with TestClient(create_app(lambda: container)) as client:
        assert (
            client.get("/internal/architecture-mapping/stats", headers=SERVICE).status_code == 404
        )
        assert not any(
            path.startswith("/internal") for path in client.get("/openapi.json").json()["paths"]
        )


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer " + "x" * 40}, {"X-Fake-Actor-Id": "fake-owner"}],
)
def test_only_the_knowledge_service_token_is_admitted(
    internal: tuple[TestClient, LibraryView], headers: dict[str, str]
) -> None:
    client, _ = internal
    response = client.get("/internal/architecture-mapping/stats", headers=headers)
    assert response.status_code == 401
    assert client.get("/internal/architecture-mapping/stats", headers=SERVICE).status_code == 200


def test_a_document_owner_sees_dependents_and_impact_through_the_service(
    internal: tuple[TestClient, LibraryView],
) -> None:
    client, document = internal
    owner = FAKE_ACTORS[0].id.value
    dependents = client.get(
        f"/internal/references/{document.id}/dependents",
        params={"actor_id": owner, "target_kind": "proposal"},
        headers=SERVICE,
    )
    assert dependents.status_code == 200
    page = dependents.json()
    assert page["next_offset"] is None
    assert page["items"] and all(item["target_kind"] == "proposal" for item in page["items"])
    assert all(item["lineage"]["citation"]["document_id"] == document.id for item in page["items"])

    impact = client.get(
        f"/internal/references/{document.id}/impact",
        params={"actor_id": owner, "limit": 100},
        headers=SERVICE,
    )
    assert impact.status_code == 200 and impact.json()["items"]
    # Ownership is checked again on this side: another person is refused.
    other = client.get(
        f"/internal/references/{document.id}/impact",
        params={"actor_id": FAKE_ACTORS[1].id.value},
        headers=SERVICE,
    )
    assert other.status_code == 403


def test_another_persons_dependents_stay_private(
    internal: tuple[TestClient, LibraryView],
) -> None:
    client, document = internal
    observer = client.get(
        f"/internal/references/{document.id}/dependents",
        params={"actor_id": FAKE_ACTORS[2].id.value},
        headers=SERVICE,
    )
    assert observer.status_code == 200
    assert observer.json()["items"] == []


def test_mapping_counts_and_actors(internal: tuple[TestClient, LibraryView]) -> None:
    client, _ = internal
    stats = client.get("/internal/architecture-mapping/stats", headers=SERVICE).json()
    assert all(set(row) == {"release_id", "requirements", "features", "stories"} for row in stats)
    owner = FAKE_ACTORS[0]
    actor = client.get(f"/internal/actors/{owner.id.value}", headers=SERVICE)
    assert actor.status_code == 200
    assert actor.json() == {
        "id": owner.id.value,
        "display_name": owner.display_name,
        "email": owner.email,
        "roles": sorted(owner.roles),
    }
    assert client.get("/internal/actors/nobody", headers=SERVICE).status_code == 404
    assert (
        client.get(
            f"/internal/references/x/dependents?actor_id={'a' * 201}", headers=SERVICE
        ).status_code
        == 422
    )


def test_the_service_token_is_read_from_the_environment_kept_secret_and_long_enough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("KNOWLEDGE_SERVICE_TOKEN", TOKEN)
    settings = Settings.from_env()
    assert settings.knowledge_service_token == TOKEN
    assert TOKEN not in repr(settings)
    monkeypatch.setenv("KNOWLEDGE_SERVICE_TOKEN", "short")
    with pytest.raises(ConfigurationError, match="KNOWLEDGE_SERVICE_TOKEN"):
        Settings.from_env()
    monkeypatch.setenv("KNOWLEDGE_SERVICE_TOKEN", "  ")
    assert Settings.from_env().knowledge_service_token is None


def test_the_router_refuses_a_request_the_middleware_did_not_admit() -> None:
    """The second wall, should the internal routes ever run without the middleware."""
    unchecked = Request({"type": "http", "headers": []})
    with pytest.raises(HTTPException) as refused:
        require_service_caller(unchecked)
    assert refused.value.status_code == 401
    admitted = Request({"type": "http", "headers": [], CALLER_SCOPE_KEY: "knowledge"})
    assert require_service_caller(admitted) == "knowledge"
