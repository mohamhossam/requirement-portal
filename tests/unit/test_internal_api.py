"""Requirement work's internal API for the knowledge service (ADR-0099)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import date

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from smb_kernel.http.service_auth import CALLER_SCOPE_KEY

from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.config.options import ConfigurationError
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.dependencies import require_service_caller
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirementInput,
)
from tests.knowledge_doubles import sync
from tests.unit import test_reference_grounding
from tests.unit.test_reference_grounding import Grounded

grounded = test_reference_grounding.grounded
TOKEN = "k" * 40
SERVICE = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def internal(grounded: Grounded) -> Iterator[tuple[TestClient, str]]:
    """A service-token client, and the policy a Requirement now cites."""
    container = grounded.container
    owner = FAKE_ACTORS[0]
    requirement = container.create_requirement.execute(
        CreateRequirementInput("Cites the policy", "XGPON coverage for bundles."), owner
    )
    container.analyze_requirement.execute(owner, requirement.id)
    serving = replace(
        container, settings=replace(container.settings, knowledge_service_token=TOKEN)
    )
    with TestClient(create_app(lambda: serving)) as client:
        yield client, grounded.citation.document_id


def test_without_a_token_the_internal_api_is_not_served(
    grounded: Grounded,
) -> None:
    container = grounded.container
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
    internal: tuple[TestClient, str], headers: dict[str, str]
) -> None:
    client, _ = internal
    response = client.get("/internal/architecture-mapping/stats", headers=headers)
    assert response.status_code == 401
    assert client.get("/internal/architecture-mapping/stats", headers=SERVICE).status_code == 200


def test_a_document_owner_sees_dependents_and_impact_through_the_service(
    internal: tuple[TestClient, str],
) -> None:
    client, document_id = internal
    owner = FAKE_ACTORS[0].id.value
    dependents = client.get(
        f"/internal/references/{document_id}/dependents",
        params={"actor_id": owner, "target_kind": "proposal"},
        headers=SERVICE,
    )
    assert dependents.status_code == 200
    page = dependents.json()
    assert page["next_offset"] is None
    assert page["items"] and all(item["target_kind"] == "proposal" for item in page["items"])
    assert all(item["lineage"]["citation"]["document_id"] == document_id for item in page["items"])

    impact = client.get(
        f"/internal/references/{document_id}/impact",
        params={"actor_id": owner, "limit": 100},
        headers=SERVICE,
    )
    assert impact.status_code == 200 and impact.json()["items"]
    # Ownership is checked again on this side: another person is refused.
    other = client.get(
        f"/internal/references/{document_id}/impact",
        params={"actor_id": FAKE_ACTORS[1].id.value},
        headers=SERVICE,
    )
    assert other.status_code == 403


def test_another_persons_dependents_stay_private(
    internal: tuple[TestClient, str],
) -> None:
    client, document_id = internal
    observer = client.get(
        f"/internal/references/{document_id}/dependents",
        params={"actor_id": FAKE_ACTORS[2].id.value},
        headers=SERVICE,
    )
    assert observer.status_code == 200
    assert observer.json()["items"] == []


def test_citation_counts_count_requirements_across_the_portfolio(grounded: Grounded) -> None:
    """A number per document, whoever owns the Requirements, and never which ones."""
    container = grounded.container
    for owner, title in ((FAKE_ACTORS[0], "Cites the policy"), (FAKE_ACTORS[1], "Cites it too")):
        requirement = container.create_requirement.execute(
            CreateRequirementInput(title, "XGPON coverage for bundles."), owner
        )
        container.analyze_requirement.execute(owner, requirement.id)
        # Analysing again supersedes the rows; it does not cite the document twice.
        container.analyze_requirement.execute(owner, requirement.id, force=True)
    serving = replace(
        container, settings=replace(container.settings, knowledge_service_token=TOKEN)
    )
    document_id = grounded.citation.document_id
    with TestClient(create_app(lambda: serving)) as client:
        response = client.get(
            "/internal/references/citation-counts",
            params={"document_id": [document_id, "unknown"]},
            headers=SERVICE,
        )
        assert response.status_code == 200
        assert response.json() == {"counts": {document_id: 2, "unknown": 0}}
        assert client.get("/internal/references/citation-counts").status_code == 401
        assert (
            client.get("/internal/references/citation-counts", headers=SERVICE).status_code == 422
        )
        too_many = {"document_id": [f"d{n}" for n in range(101)]}
        assert (
            client.get(
                "/internal/references/citation-counts", params=too_many, headers=SERVICE
            ).status_code
            == 422
        )
        too_long = {"document_id": ["d" * 201]}
        assert (
            client.get(
                "/internal/references/citation-counts", params=too_long, headers=SERVICE
            ).status_code
            == 422
        )


def test_mapping_counts_and_bounded_actor_ids(internal: tuple[TestClient, str]) -> None:
    client, _ = internal
    stats = client.get("/internal/architecture-mapping/stats", headers=SERVICE).json()
    assert all(set(row) == {"release_id", "requirements", "features", "stories"} for row in stats)
    # People are the identity service's to describe; requirement work no longer serves them.
    assert client.get("/internal/actors/fake-owner", headers=SERVICE).status_code == 404
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


def test_a_cited_document_past_its_review_date_is_flagged_beside_its_proposal(
    grounded: Grounded,
) -> None:
    """Knowledge Center D: worked out when read, from the library's due date; never a block."""
    container, owner = grounded.container, FAKE_ACTORS[0]
    requirement = container.create_requirement.execute(
        CreateRequirementInput("Cites the policy", "XGPON coverage for bundles."), owner
    )
    container.analyze_requirement.execute(owner, requirement.id)
    workspace = container.analysis_collaboration.workspace(requirement.id)
    assert workspace.overdue_reference_reviews == {}
    document_id = grounded.citation.document_id
    grounded.library.falls_due(document_id, date(2026, 1, 1))
    sync(container)
    later = container.analysis_collaboration.workspace(requirement.id)
    assert later.overdue_reference_reviews == {document_id: date(2026, 1, 1)}
    # A due date still ahead is not flagged.
    grounded.library.falls_due(document_id, date(2099, 1, 1))
    sync(container)
    assert (
        container.analysis_collaboration.workspace(requirement.id).overdue_reference_reviews == {}
    )
