"""Slice 8A actor, ownership, assignment, and authorization behavior."""

from dataclasses import replace
from datetime import UTC, datetime
from threading import Thread

import pytest
from fastapi.testclient import TestClient
from smb_kernel.identity.ports import IdentityCredential

from smb_requirement_agent.application.errors import (
    AuthenticationRequiredError,
    IdentityProviderUnavailableError,
)
from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirementInput
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementPermission,
)
from smb_requirement_agent.domain.identity.entities import ActorId, ActorProfile, RequirementAccess
from smb_requirement_agent.domain.identity.errors import (
    AuthorizationDeniedError,
    InvalidIdentityError,
    RequirementAccessConflictError,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.infrastructure.config.options import IdentityProvider, LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.persistence.in_memory_identity import (
    InMemoryAccessRepository,
)
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from tests.conftest import FAKE_PROVIDER_SETTINGS
from tests.unit.workflow_helpers import post_analysis, screen_current_knowledge

NOW = datetime(2026, 9, 3, 12, tzinfo=UTC)


def test_access_invariants_and_idempotent_reviewer_changes() -> None:
    owner, reviewer, observer = FAKE_ACTORS
    access = RequirementAccess(RequirementId("requirement-1")).claim(owner, NOW)

    with pytest.raises(RequirementAccessConflictError):
        access.assign_reviewer(owner, owner, NOW)
    with pytest.raises(AuthorizationDeniedError):
        access.assign_reviewer(observer, reviewer, NOW)

    assigned = access.assign_reviewer(owner, reviewer, NOW)
    assert assigned.assign_reviewer(owner, reviewer, NOW) == assigned
    assert assigned.remove_reviewer(owner, ActorId("not-assigned"), NOW) == assigned


def test_transfer_removes_recipient_from_reviewers_and_drops_prior_owner() -> None:
    owner, reviewer, _ = FAKE_ACTORS
    access = (
        RequirementAccess(RequirementId("requirement-1"))
        .claim(owner, NOW)
        .assign_reviewer(owner, reviewer, NOW)
        .transfer(owner, reviewer, NOW)
    )

    assert access.owner is not None and access.owner.actor.id == reviewer.id
    assert access.reviewers == ()
    assert not access.includes(owner.id)


def test_requirement_and_actor_ids_reject_blank_values() -> None:
    with pytest.raises(InvalidIdentityError):
        ActorId("  ")
    with pytest.raises(Exception, match="must not be blank"):
        RequirementId("  ")


def test_in_memory_repository_rejects_competing_claims() -> None:
    repository = InMemoryAccessRepository()
    requirement_id = RequirementId("legacy")
    owner_claim = RequirementAccess(requirement_id).claim(FAKE_ACTORS[0], NOW)
    competing_claim = RequirementAccess(requirement_id).claim(FAKE_ACTORS[1], NOW)
    repository.save_requirement(owner_claim)

    with pytest.raises(RequirementAccessConflictError):
        repository.save_requirement(competing_claim)


def test_member_mutation_rechecks_access_after_external_work(container: Container) -> None:
    owner, reviewer, _ = FAKE_ACTORS
    requirement = container.create_requirement.execute(
        CreateRequirementInput("Authorization race", "Reviewer access changes mid-generation."),
        owner,
    )
    current_access = container.access_repository.get_requirement(requirement.id)
    assert current_access is not None
    assigned = container.requirement_access.assign_reviewer(
        requirement.id,
        owner,
        reviewer.id,
        expected_version=current_access.version,
    )
    concurrent_errors: list[BaseException] = []

    def revoke_reviewer() -> None:
        try:
            container.requirement_access.remove_reviewer(
                requirement.id,
                owner,
                reviewer.id,
                expected_version=assigned.access.version,
            )
        except BaseException as exc:  # expose failures from the concurrent actor
            concurrent_errors.append(exc)

    def provider_backed_operation() -> None:
        with container.transaction_manager.external_call():
            concurrent = Thread(target=revoke_reviewer)
            concurrent.start()
            concurrent.join()

    with pytest.raises(AuthorizationDeniedError):
        container.requirement_access.execute_mutation(
            requirement.id,
            reviewer,
            RequirementPermission.MEMBER,
            provider_backed_operation,
        )

    assert concurrent_errors == []
    persisted = container.access_repository.get_requirement(requirement.id)
    assert persisted is not None
    assert not persisted.includes(reviewer.id)


def test_reviewer_cannot_control_an_automatic_job(container: Container) -> None:
    owner, reviewer, _ = FAKE_ACTORS
    requirement = container.create_requirement.execute(
        CreateRequirementInput("Automatic job ownership", "Only the owner controls system work."),
        owner,
    )
    current_access = container.access_repository.get_requirement(requirement.id)
    assert current_access is not None
    container.requirement_access.assign_reviewer(
        requirement.id,
        owner,
        reviewer.id,
        expected_version=current_access.version,
    )

    with pytest.raises(AuthorizationDeniedError):
        container.requirement_access.require_job_controller(
            requirement.id,
            reviewer.id,
            ActorId("system-automation"),
            automatic=True,
        )

    controlled = container.requirement_access.require_job_controller(
        requirement.id,
        owner.id,
        ActorId("system-automation"),
        automatic=True,
    )
    assert controlled.is_owner(owner.id)


def test_assignment_routes_and_assigned_to_me_are_actor_scoped(client: TestClient) -> None:
    created = client.post("/requirements", json={"title": "Identity", "description": "Test"})
    requirement_id = created.json()["id"]
    post_analysis(client, requirement_id)

    initial = client.get(f"/requirements/{requirement_id}/assignments")
    assert initial.status_code == 200
    assert initial.json()["owner"]["actor"]["id"] == "fake-owner"
    assert initial.json()["can_manage_assignments"] is True

    assigned = client.put(
        f"/requirements/{requirement_id}/reviewers/fake-reviewer",
        json={"expected_version": initial.json()["version"]},
    )
    assert assigned.status_code == 200
    assert [item["actor"]["id"] for item in assigned.json()["reviewers"]] == ["fake-reviewer"]

    reviewer_headers = {"X-Fake-Actor-Id": "fake-reviewer"}
    mine = client.get("/requirements?assigned_to_me=true", headers=reviewer_headers)
    assert [item["id"] for item in mine.json()["requirements"]] == [requirement_id]
    denied = client.post(
        f"/requirements/{requirement_id}/analysis/confirmation",
        json={
            "expected_version": client.get(f"/requirements/{requirement_id}/analysis").json()[
                "version"
            ]
        },
        headers=reviewer_headers,
    )
    assert denied.status_code == 403
    assert (
        client.put(
            f"/requirements/{requirement_id}/reviewers/fake-observer",
            json={"expected_version": assigned.json()["version"]},
            headers=reviewer_headers,
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/requirements/{requirement_id}/reviewers/not-known",
            json={"expected_version": assigned.json()["version"]},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/requirements/{requirement_id}/ownership/claim",
            json={"expected_version": assigned.json()["version"]},
            headers=reviewer_headers,
        ).status_code
        == 409
    )
    assert client.get("/requirements/missing/assignments").status_code == 404

    transferred = client.put(
        f"/requirements/{requirement_id}/ownership",
        json={
            "actor_id": "fake-reviewer",
            "expected_version": assigned.json()["version"],
        },
    )
    assert transferred.status_code == 200
    assert transferred.json()["owner"]["actor"]["id"] == "fake-reviewer"
    assert transferred.json()["reviewers"] == []
    assert client.get("/requirements?assigned_to_me=true").json()["requirements"] == []


def test_identity_routes_fake_header_validation_and_known_actor_lookup(client: TestClient) -> None:
    config = client.get("/identity/config")
    assert config.status_code == 200
    assert config.json()["mode"] == "fake"
    assert len(config.json()["fake_actors"]) == 3
    assert config.json()["login_choices"] == []
    assert client.get("/identity/me").json()["id"] == "fake-owner"
    assert [item["id"] for item in client.get("/identity/actors?q=ravi").json()] == [
        "fake-reviewer"
    ]
    invalid = client.get("/requirements", headers={"X-Fake-Actor-Id": "unknown"})
    assert invalid.status_code == 401
    assert invalid.headers["www-authenticate"] == "Bearer"


def test_identity_config_exposes_ordered_keycloak_login_choices() -> None:
    settings = Settings(
        llm_provider=LLMProvider.FAKE,
        identity_provider=IdentityProvider.OIDC,
        oidc_issuer_url="https://identity.example.test/realms/requirement-ai",
        oidc_audience="requirement-api",
        oidc_client_id="requirement-spa",
        oidc_company_sso_alias="entra-company",
    )
    container = build_container(settings)
    with TestClient(create_app(lambda: container)) as client:
        response = client.get("/identity/config")

    assert response.status_code == 200
    assert response.json()["fake_actors"] == []
    assert response.json()["login_choices"] == [
        {
            "id": "microsoft",
            "label": "Continue with Microsoft",
            "authorization_parameters": {"kc_idp_hint": "entra-company"},
        },
        {
            "id": "password",
            "label": "Continue with email and password",
            "authorization_parameters": {},
        },
    ]


def test_analysis_confirmation_records_the_owner_snapshot(
    client: TestClient, container: Container
) -> None:
    created = client.post(
        "/requirements",
        json={
            "title": "Attribution",
            "description": "Test",
            "desired_outcome": "The attribution is recorded.",
        },
    )
    requirement_id = created.json()["id"]
    post_analysis(client, requirement_id)
    analysis = container.analysis_repository.get_by_requirement_id(RequirementId(requirement_id))
    assert analysis is not None
    container.analysis_repository.save(
        replace(
            analysis,
            assumptions=(),
            open_questions=(),
            ambiguities=(),
            potential_dependencies=(),
            version=analysis.version + 1,
        )
    )
    for question in container.analysis_audit_repository.list_questions(
        RequirementId(requirement_id)
    ):
        container.analysis_audit_repository.save_question(question.supersede())

    screen_current_knowledge(client, requirement_id)
    current = client.get(f"/requirements/{requirement_id}/analysis").json()
    response = client.post(
        f"/requirements/{requirement_id}/analysis/confirmation",
        json={"expected_version": current["version"]},
    )

    assert response.status_code == 200
    assert response.json()["confirmed_by"]["id"] == "fake-owner"


def test_drafts_are_owner_scoped(client: TestClient) -> None:
    body = {
        "title": "Owned draft",
        "description": "",
        "desired_outcome": "",
        "customer_context": "",
        "channels": [],
        "systems": [],
        "business_rules": [],
        "constraints": [],
    }
    created = client.post("/requirements/drafts", json=body)
    draft_id = created.json()["id"]

    reviewer_headers = {"X-Fake-Actor-Id": "fake-reviewer"}
    assert client.get("/requirements/drafts", headers=reviewer_headers).json() == []
    assert (
        client.get(f"/requirements/drafts/{draft_id}", headers=reviewer_headers).status_code == 403
    )
    assert (
        client.post(
            f"/requirements/drafts/{draft_id}/promote",
            json={"expected_version": 1},
            headers=reviewer_headers,
        ).status_code
        == 403
    )


class _BearerIdentity:
    def authenticate(self, credential: IdentityCredential) -> ActorProfile:
        if credential.bearer_token != "valid-token":
            raise AuthenticationRequiredError("A valid bearer token is required.")
        return ActorProfile(ActorId("opaque-actor"), "OIDC Actor", "actor@example.test")


class _UnavailableIdentity:
    def authenticate(self, credential: IdentityCredential) -> ActorProfile:
        del credential
        raise IdentityProviderUnavailableError("Identity provider unavailable.")


def test_oidc_mode_requires_bearer_and_rejects_fake_actor_header() -> None:
    settings = replace(
        FAKE_PROVIDER_SETTINGS,
        identity_provider=IdentityProvider.OIDC,
        oidc_issuer_url="https://identity.example.test",
        oidc_audience="requirement-api",
        oidc_client_id="spa-client",
        oidc_allowed_algorithms=("RS256",),
    )
    container = build_container(settings, identity_provider=_BearerIdentity())
    with TestClient(create_app(lambda: container)) as oidc_client:
        missing = oidc_client.get("/requirements")
        assert missing.status_code == 401
        assert missing.headers["www-authenticate"] == "Bearer"
        rejected = oidc_client.get(
            "/requirements",
            headers={
                "Authorization": "Bearer valid-token",
                "X-Fake-Actor-Id": "fake-owner",
            },
        )
        assert rejected.status_code == 401
        assert (
            oidc_client.get(
                "/requirements", headers={"Authorization": "Bearer valid-token"}
            ).status_code
            == 200
        )


def test_identity_provider_unavailability_maps_to_503() -> None:
    settings = replace(
        FAKE_PROVIDER_SETTINGS,
        identity_provider=IdentityProvider.OIDC,
        oidc_issuer_url="https://identity.example.test",
        oidc_audience="requirement-api",
        oidc_client_id="spa-client",
        oidc_allowed_algorithms=("RS256",),
    )
    container = build_container(settings, identity_provider=_UnavailableIdentity())
    with TestClient(create_app(lambda: container)) as oidc_client:
        assert (
            oidc_client.get("/requirements", headers={"Authorization": "Bearer token"}).status_code
            == 503
        )


def test_offline_personas_match_the_knowledge_portal_admins(client: TestClient) -> None:
    """The same two personas are knowledge admins in knowledge-portal's fake identity."""
    admins = {
        actor_id
        for actor_id in ("fake-owner", "fake-reviewer", "fake-observer")
        if "knowledge_admin"
        in client.get("/identity/me", headers={"X-Fake-Actor-Id": actor_id}).json()["roles"]
    }

    assert admins == {"fake-owner", "fake-reviewer"}
