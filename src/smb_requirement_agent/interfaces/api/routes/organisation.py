"""The organisation catalogue: value streams, products, squads and people.

Routes translate HTTP to use-case calls and domain results to API schemas.
Authorization is decided by the use cases, never here.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from smb_requirement_agent.application.use_cases.organisation_catalogue import (
    ManageOrganisationCatalogue,
)
from smb_requirement_agent.domain.organisation.catalogue import InvalidOrganisationError
from smb_requirement_agent.interfaces.api.dependencies import (
    KnowledgeActorDep,
    get_manage_organisation_catalogue,
)
from smb_requirement_agent.interfaces.api.schemas.organisation import (
    OrganisationAuditEventResponse,
    OrganisationResponse,
    PersonRequest,
    ProductRequest,
    RemovalRequest,
    SquadRequest,
    SystemOwnershipResponse,
    ValueStreamRequest,
)

router = APIRouter(prefix="/organisation", tags=["organisation"])

OrganisationDep = Annotated[ManageOrganisationCatalogue, Depends(get_manage_organisation_catalogue)]


def _same_id(path_id: str, body_id: str) -> None:
    if path_id != body_id:
        raise InvalidOrganisationError("The path and body identify different records.")


@router.get("", response_model=OrganisationResponse)
def view(organisation: OrganisationDep, actor: KnowledgeActorDep) -> OrganisationResponse:
    return OrganisationResponse.from_domain(organisation.view(actor))


@router.get("/audit", response_model=list[OrganisationAuditEventResponse])
def audit(
    organisation: OrganisationDep, actor: KnowledgeActorDep
) -> list[OrganisationAuditEventResponse]:
    return [OrganisationAuditEventResponse.from_domain(item) for item in organisation.audit(actor)]


@router.get("/systems/{system_id}/ownership", response_model=SystemOwnershipResponse)
def system_ownership(
    system_id: str, organisation: OrganisationDep, actor: KnowledgeActorDep
) -> SystemOwnershipResponse:
    return SystemOwnershipResponse.from_domain(organisation.ownership(system_id, actor))


@router.post("/people", response_model=OrganisationResponse, status_code=201)
def create_person(
    body: PersonRequest, organisation: OrganisationDep, actor: KnowledgeActorDep
) -> OrganisationResponse:
    return OrganisationResponse.from_domain(
        organisation.save_person(body.person.to_domain(), None, actor)
    )


@router.put("/people/{person_id}", response_model=OrganisationResponse)
def update_person(
    person_id: str, body: PersonRequest, organisation: OrganisationDep, actor: KnowledgeActorDep
) -> OrganisationResponse:
    _same_id(person_id, body.person.id)
    return OrganisationResponse.from_domain(
        organisation.save_person(body.person.to_domain(), _revision(body.expected_revision), actor)
    )


@router.post("/value-streams", response_model=OrganisationResponse, status_code=201)
def create_value_stream(
    body: ValueStreamRequest, organisation: OrganisationDep, actor: KnowledgeActorDep
) -> OrganisationResponse:
    return OrganisationResponse.from_domain(
        organisation.save_value_stream(body.value_stream.to_domain(), None, actor)
    )


@router.put("/value-streams/{value_stream_id}", response_model=OrganisationResponse)
def update_value_stream(
    value_stream_id: str,
    body: ValueStreamRequest,
    organisation: OrganisationDep,
    actor: KnowledgeActorDep,
) -> OrganisationResponse:
    _same_id(value_stream_id, body.value_stream.id)
    return OrganisationResponse.from_domain(
        organisation.save_value_stream(
            body.value_stream.to_domain(), _revision(body.expected_revision), actor
        )
    )


@router.delete("/value-streams/{value_stream_id}", response_model=OrganisationResponse)
def remove_value_stream(
    value_stream_id: str,
    body: RemovalRequest,
    organisation: OrganisationDep,
    actor: KnowledgeActorDep,
) -> OrganisationResponse:
    return OrganisationResponse.from_domain(
        organisation.remove_value_stream(value_stream_id, body.expected_revision, actor)
    )


@router.post("/products", response_model=OrganisationResponse, status_code=201)
def create_product(
    body: ProductRequest, organisation: OrganisationDep, actor: KnowledgeActorDep
) -> OrganisationResponse:
    return OrganisationResponse.from_domain(
        organisation.save_product(body.product.to_domain(), None, actor)
    )


@router.put("/products/{product_id}", response_model=OrganisationResponse)
def update_product(
    product_id: str, body: ProductRequest, organisation: OrganisationDep, actor: KnowledgeActorDep
) -> OrganisationResponse:
    _same_id(product_id, body.product.id)
    return OrganisationResponse.from_domain(
        organisation.save_product(
            body.product.to_domain(), _revision(body.expected_revision), actor
        )
    )


@router.delete("/products/{product_id}", response_model=OrganisationResponse)
def remove_product(
    product_id: str, body: RemovalRequest, organisation: OrganisationDep, actor: KnowledgeActorDep
) -> OrganisationResponse:
    return OrganisationResponse.from_domain(
        organisation.remove_product(product_id, body.expected_revision, actor)
    )


@router.post("/squads", response_model=OrganisationResponse, status_code=201)
def create_squad(
    body: SquadRequest, organisation: OrganisationDep, actor: KnowledgeActorDep
) -> OrganisationResponse:
    return OrganisationResponse.from_domain(
        organisation.save_squad(body.squad.to_domain(), None, actor)
    )


@router.put("/squads/{squad_id}", response_model=OrganisationResponse)
def update_squad(
    squad_id: str, body: SquadRequest, organisation: OrganisationDep, actor: KnowledgeActorDep
) -> OrganisationResponse:
    _same_id(squad_id, body.squad.id)
    return OrganisationResponse.from_domain(
        organisation.save_squad(body.squad.to_domain(), _revision(body.expected_revision), actor)
    )


@router.delete("/squads/{squad_id}", response_model=OrganisationResponse)
def remove_squad(
    squad_id: str, body: RemovalRequest, organisation: OrganisationDep, actor: KnowledgeActorDep
) -> OrganisationResponse:
    return OrganisationResponse.from_domain(
        organisation.remove_squad(squad_id, body.expected_revision, actor)
    )


def _revision(expected_revision: int | None) -> int:
    if expected_revision is None:
        raise InvalidOrganisationError("Updating a record requires its expected revision.")
    return expected_revision
