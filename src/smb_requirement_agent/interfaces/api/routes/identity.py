"""Authenticated actor and Requirement assignment endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from smb_requirement_agent.interfaces.api.dependencies import (
    ContainerDep,
    CurrentActorDep,
    get_requirement_access,
    get_search_known_actors,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.schemas.identity import (
    AccessChangeResponse,
    AccessMutationRequest,
    ActorResponse,
    AssignmentResponse,
    IdentityConfigResponse,
    LoginChoiceResponse,
    RequirementAccessResponse,
    TransferOwnershipRequest,
)
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
    ActorSnapshot,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.workflows.application.use_cases.identity_access import (
    RequirementAccessService,
    RequirementAccessView,
    SearchKnownActors,
)

public_router = APIRouter(prefix="/identity", tags=["identity"])
router = APIRouter(
    prefix="/identity", tags=["identity"], dependencies=[Depends(require_authenticated_actor)]
)
assignment_router = APIRouter(
    prefix="/requirements",
    tags=["identity"],
    dependencies=[Depends(require_authenticated_actor)],
)


def actor_response(actor: ActorProfile | ActorSnapshot) -> ActorResponse:
    return ActorResponse(
        id=actor.id.value,
        display_name=actor.display_name,
        email=actor.email,
        roles=sorted(actor.roles) if isinstance(actor, ActorProfile) else [],
    )


def access_response(view: RequirementAccessView) -> RequirementAccessResponse:
    value = view.access
    return RequirementAccessResponse(
        requirement_id=value.requirement_id.value,
        version=value.version,
        owner=(
            AssignmentResponse(
                actor=actor_response(value.owner.actor),
                role=value.owner.role,
                assigned_at=value.owner.assigned_at,
                assigned_by=actor_response(value.owner.assigned_by),
            )
            if value.owner
            else None
        ),
        reviewers=[
            AssignmentResponse(
                actor=actor_response(item.actor),
                role=item.role,
                assigned_at=item.assigned_at,
                assigned_by=actor_response(item.assigned_by),
            )
            for item in value.reviewers
        ],
        changes=[
            AccessChangeResponse(
                kind=item.kind,
                actor=actor_response(item.actor),
                performed_by=actor_response(item.performed_by),
                recorded_at=item.recorded_at,
            )
            for item in value.changes
        ],
        can_claim_owner=view.can_claim_owner,
        can_manage_assignments=view.can_manage_assignments,
        can_confirm_analysis=view.can_confirm_analysis,
        can_export_approved_revisions=view.can_export_approved_revisions,
        can_manage_content=view.can_manage_content,
        can_govern=view.can_govern,
    )


@public_router.get("/config", response_model=IdentityConfigResponse)
def identity_config(container: ContainerDep) -> IdentityConfigResponse:
    settings = container.settings
    fake_actors = (
        [actor_response(item) for item in container.actor_directory.search(None, 100)]
        if settings.identity_provider.value == "fake"
        else []
    )
    login_choices: list[LoginChoiceResponse] = []
    if settings.identity_provider.value == "oidc":
        if settings.oidc_company_sso_enabled:
            login_choices.append(
                LoginChoiceResponse(
                    id="microsoft",
                    label="Continue with Microsoft",
                    authorization_parameters={"kc_idp_hint": settings.oidc_company_sso_alias},
                )
            )
        if settings.oidc_password_login_enabled:
            login_choices.append(
                LoginChoiceResponse(
                    id="password",
                    label="Continue with email and password",
                    authorization_parameters={},
                )
            )
    return IdentityConfigResponse(
        mode=settings.identity_provider,
        authority=settings.oidc_issuer_url or None,
        audience=settings.oidc_audience or None,
        client_id=settings.oidc_client_id or None,
        scopes=settings.oidc_scopes if settings.identity_provider.value == "oidc" else None,
        fake_actors=fake_actors,
        login_choices=login_choices,
    )


@router.get("/me", response_model=ActorResponse)
def current_actor(actor: CurrentActorDep) -> ActorResponse:
    return actor_response(actor)


@router.get("/actors", response_model=list[ActorResponse])
def search_actors(
    actor: CurrentActorDep,
    use_case: Annotated[SearchKnownActors, Depends(get_search_known_actors)],
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ActorResponse]:
    del actor
    return [actor_response(item) for item in use_case.execute(q, limit)]


@assignment_router.get("/{requirement_id}/assignments", response_model=RequirementAccessResponse)
def get_assignments(
    requirement_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[RequirementAccessService, Depends(get_requirement_access)],
) -> RequirementAccessResponse:
    return access_response(use_case.requirement_view(RequirementId(requirement_id), actor))


@assignment_router.post(
    "/{requirement_id}/ownership/claim", response_model=RequirementAccessResponse
)
def claim_requirement(
    requirement_id: str,
    actor: CurrentActorDep,
    body: AccessMutationRequest,
    use_case: Annotated[RequirementAccessService, Depends(get_requirement_access)],
) -> RequirementAccessResponse:
    return access_response(
        use_case.claim_requirement(RequirementId(requirement_id), actor, body.expected_version)
    )


@assignment_router.put("/{requirement_id}/ownership", response_model=RequirementAccessResponse)
def transfer_requirement(
    requirement_id: str,
    body: TransferOwnershipRequest,
    actor: CurrentActorDep,
    use_case: Annotated[RequirementAccessService, Depends(get_requirement_access)],
) -> RequirementAccessResponse:
    return access_response(
        use_case.transfer_requirement(
            RequirementId(requirement_id), actor, ActorId(body.actor_id), body.expected_version
        )
    )


@assignment_router.put(
    "/{requirement_id}/reviewers/{actor_id}", response_model=RequirementAccessResponse
)
def assign_reviewer(
    requirement_id: str,
    actor_id: str,
    actor: CurrentActorDep,
    body: AccessMutationRequest,
    use_case: Annotated[RequirementAccessService, Depends(get_requirement_access)],
) -> RequirementAccessResponse:
    return access_response(
        use_case.assign_reviewer(
            RequirementId(requirement_id), actor, ActorId(actor_id), body.expected_version
        )
    )


@assignment_router.delete(
    "/{requirement_id}/reviewers/{actor_id}", response_model=RequirementAccessResponse
)
def remove_reviewer(
    requirement_id: str,
    actor_id: str,
    actor: CurrentActorDep,
    body: AccessMutationRequest,
    use_case: Annotated[RequirementAccessService, Depends(get_requirement_access)],
) -> RequirementAccessResponse:
    return access_response(
        use_case.remove_reviewer(
            RequirementId(requirement_id), actor, ActorId(actor_id), body.expected_version
        )
    )


@assignment_router.post("/drafts/{draft_id}/ownership/claim", response_model=AssignmentResponse)
def claim_draft(
    draft_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[RequirementAccessService, Depends(get_requirement_access)],
) -> AssignmentResponse:
    ownership = use_case.claim_draft(RequirementId(draft_id), actor)
    if ownership.owner is None:  # pragma: no cover - claim invariant
        raise AssertionError("A claimed draft must have an owner.")
    return AssignmentResponse(
        actor=actor_response(ownership.owner.actor),
        role=ownership.owner.role,
        assigned_at=ownership.owner.assigned_at,
        assigned_by=actor_response(ownership.owner.assigned_by),
    )
