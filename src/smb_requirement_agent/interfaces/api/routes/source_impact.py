"""Source impact is requirement work: how a published-source change affects its content.

They replaced `/library/requirements/{id}/source-impact` and
`/library/source-impact/{id}/decisions`, which are gone (ADR-0099). A library
owner's view of a document's dependents lives in the knowledge portal.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from smb_requirement_agent.application.use_cases.source_impact import (
    DependencyImpact,
    DependencyImpactPage,
    SourceImpactReview,
)
from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    get_source_impact,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.schemas.source_impact import ImpactDecisionRequest

router = APIRouter(
    prefix="/requirements",
    tags=["source impact"],
    dependencies=[Depends(require_authenticated_actor)],
)
ImpactDep = Annotated[SourceImpactReview, Depends(get_source_impact)]


@router.get("/{requirement_id}/source-impact")
def requirement_source_impact(
    requirement_id: str,
    actor: CurrentActorDep,
    service: ImpactDep,
    response: Response,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    active_only: bool = False,
    query: str = Query("", max_length=200),
) -> DependencyImpactPage:
    response.headers["Cache-Control"] = "private, no-store"
    return service.page(
        actor,
        requirement_id=requirement_id,
        offset=offset,
        limit=limit,
        active_only=active_only,
        query=query,
    )


@router.post("/{requirement_id}/source-impact/{dependency_id}/decisions")
def decide_requirement_source_impact(
    requirement_id: str,
    dependency_id: str,
    data: ImpactDecisionRequest,
    actor: CurrentActorDep,
    service: ImpactDep,
) -> DependencyImpact:
    return service.decide(
        dependency_id,
        actor,
        data.publication_state,
        data.expected_version,
        data.decision,
        data.reason,
        requirement_id=requirement_id,
    )
