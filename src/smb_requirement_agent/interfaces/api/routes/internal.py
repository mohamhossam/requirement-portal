"""Requirement work's internal API, for the knowledge service only (ADR-0099).

Every route needs a service token (`InternalAccess` in main.py); none needs a
signed-in user. The person the knowledge service acts for is named by
`actor_id`. These routes are not in the public OpenAPI, and the edge proxy
never routes /internal.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Query

from smb_requirement_agent.application.ports.architecture_mapping_stats import MappingCount
from smb_requirement_agent.application.use_cases.internal_reads import (
    CorpusSummary,
    DependentsPage,
    InternalReads,
)
from smb_requirement_agent.application.use_cases.source_impact import DependencyImpactPage
from smb_requirement_agent.interfaces.api.dependencies import (
    get_internal_reads,
    require_service_caller,
)

# Mounted with include_in_schema=False (main.py): the browser contract never lists
# these. `contract_openapi()` documents them on their own for the knowledge service.
router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_service_caller)],
)
ReadsDep = Annotated[InternalReads, Depends(get_internal_reads)]
ActorQuery = Annotated[str, Query(min_length=1, max_length=200)]


@router.get("/references/{document_id}/impact")
def document_impact(
    document_id: str,
    actor_id: ActorQuery,
    reads: ReadsDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    active_only: bool = False,
    query: str = Query("", max_length=200),
) -> DependencyImpactPage:
    return reads.document_impact(
        document_id,
        actor_id,
        active_only=active_only,
        query=query,
        offset=offset,
        limit=limit,
    )


@router.get("/references/{document_id}/dependents")
def document_dependents(
    document_id: str,
    actor_id: ActorQuery,
    reads: ReadsDep,
    target_kind: str | None = Query(None, max_length=40),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> DependentsPage:
    return reads.dependents(document_id, actor_id, target_kind, offset, limit)


@router.get("/architecture-mapping/stats")
def mapping_stats(reads: ReadsDep) -> list[MappingCount]:
    return list(reads.mapping_counts())


@router.get("/knowledge/corpus/summary")
def corpus_summary(reads: ReadsDep) -> CorpusSummary:
    """Requirement knowledge corpus health for the Knowledge Center: counts only."""
    return reads.corpus_summary()


def contract_openapi() -> dict[str, Any]:
    """This internal API on its own: the contract the knowledge service builds against."""
    application = FastAPI(title="Requirement service internal API")
    application.include_router(router)
    return application.openapi()
