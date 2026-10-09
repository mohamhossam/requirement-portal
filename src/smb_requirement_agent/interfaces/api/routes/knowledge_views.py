"""Read-only views of knowledge a Requirement relies on, for any signed-in member (ADR-0099).

The knowledge itself is curated in the knowledge portal; these routes only show
what is published: the exact passage a Requirement cites, the evidence behind an
architecture impact, and which catalogue version is in use. Unified search spans
the member's own Requirement knowledge and the published library together.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from smb_requirement_agent.interfaces.api.dependencies import (
    get_current_release,
    get_knowledge_views,
    get_unified_knowledge_search,
    limit_provider_calls,
    require_authenticated_actor,
)
from smb_requirement_agent.knowledge.application.use_cases.unified_knowledge_search import (
    UnifiedKnowledgeSearch,
    UnifiedSearchHit,
)
from smb_requirement_agent.references.application.ports.architecture_knowledge import ActiveRelease
from smb_requirement_agent.references.application.ports.knowledge_views import (
    ArchitectureEvidence,
    CitedPassage,
    PassageCitation,
)
from smb_requirement_agent.references.application.use_cases.knowledge_views import KnowledgeViews
from smb_requirement_agent.references.application.use_cases.reference_currency import (
    CurrentArchitectureRelease,
)

router = APIRouter(tags=["knowledge views"], dependencies=[Depends(require_authenticated_actor)])
# Set on a unified search answered without the reference library (ADR-0104).
REFERENCE_LIBRARY_HEADER = "X-Reference-Library"
ViewsDep = Annotated[KnowledgeViews, Depends(get_knowledge_views)]
ReleaseDep = Annotated[CurrentArchitectureRelease, Depends(get_current_release)]
Identifier = Annotated[str, Query(min_length=1, max_length=200)]


@router.get("/references/passage")
def cited_passage(
    views: ViewsDep,
    response: Response,
    document_id: Identifier,
    publication_id: Identifier,
    version_id: Identifier,
    revision_id: Identifier,
    block_id: Identifier,
) -> CitedPassage:
    """The exact published passage a Requirement cites, while it is still published."""
    response.headers["Cache-Control"] = "private, no-store"
    return views.passage(
        PassageCitation(document_id, publication_id, version_id, revision_id, block_id)
    )


@router.get("/architecture-evidence/{release_id}/{chunk_id}")
def architecture_evidence(
    release_id: str, chunk_id: str, views: ViewsDep, response: Response
) -> ArchitectureEvidence:
    """The catalogue evidence behind an architecture impact, from a published version."""
    response.headers["Cache-Control"] = "private, no-store"
    return views.evidence(release_id, chunk_id)


@router.get("/architecture/active-release")
def active_release(release: ReleaseDep) -> ActiveRelease | None:
    """The catalogue version new mappings use; null until the first one is known."""
    return release.active_release()


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


@router.post("/knowledge/search/unified", dependencies=[Depends(limit_provider_calls)])
def unified_search(
    data: KnowledgeSearchRequest,
    response: Response,
    service: Annotated[UnifiedKnowledgeSearch, Depends(get_unified_knowledge_search)],
) -> tuple[UnifiedSearchHit, ...]:
    """Requirement knowledge the member may see, and published library passages (ADR-0075).

    With a connected knowledge portal that cannot be reached, the hits are Requirements only
    and `X-Reference-Library: unavailable` says so; the body keeps its shape.
    """
    result = service.execute(data.query)
    if result.references_unavailable:
        response.headers[REFERENCE_LIBRARY_HEADER] = "unavailable"
    return result.hits
