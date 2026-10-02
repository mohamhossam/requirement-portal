"""Read-only views of knowledge a Requirement relies on, for any signed-in member (ADR-0099).

The knowledge itself is curated in the knowledge portal; these routes only show
what is published: the exact passage a Requirement cites, the evidence behind an
architecture impact, and which catalogue version is in use.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from smb_requirement_agent.application.ports.architecture_knowledge import ActiveRelease
from smb_requirement_agent.application.ports.knowledge_views import (
    ArchitectureEvidence,
    CitedPassage,
    PassageCitation,
)
from smb_requirement_agent.application.use_cases.knowledge_views import KnowledgeViews
from smb_requirement_agent.application.use_cases.reference_currency import (
    CurrentArchitectureRelease,
)
from smb_requirement_agent.interfaces.api.dependencies import (
    get_current_release,
    get_knowledge_views,
    require_authenticated_actor,
)

router = APIRouter(tags=["knowledge views"], dependencies=[Depends(require_authenticated_actor)])
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
