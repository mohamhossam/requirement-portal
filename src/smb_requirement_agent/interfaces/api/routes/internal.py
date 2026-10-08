"""Requirement work's internal API, for the knowledge service only (ADR-0099).

Every route needs a service token (`InternalAccess` in main.py); none needs a
signed-in user. The person the knowledge service acts for is named by
`actor_id`. These routes are not in the public OpenAPI, and the edge proxy
never routes /internal.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, FastAPI, Path, Query
from pydantic import BaseModel, Field

from smb_requirement_agent.application.ports.knowledge_portfolio import FindingAge, IndexState
from smb_requirement_agent.application.use_cases.corpus_actions import (
    REINDEX_MAX,
    BulkReindexRequirements,
    BulkResult,
    MembershipResult,
    ReinstateToCorpus,
    RetireFromCorpus,
)
from smb_requirement_agent.application.use_cases.knowledge_portfolio import (
    CorpusPage,
    FindingsPage,
    KnowledgePortfolio,
    NudgeFindingOwners,
    NudgeResult,
)
from smb_requirement_agent.application.use_cases.prior_art import HistoricCitations
from smb_requirement_agent.application.use_cases.source_impact import DependencyImpactPage
from smb_requirement_agent.breakdown.application.ports.architecture_mapping_stats import (
    MappingCount,
)
from smb_requirement_agent.domain.knowledge.entities import KnowledgeRelationshipKind
from smb_requirement_agent.domain.knowledge.membership import REASON_MAX
from smb_requirement_agent.interfaces.api.dependencies import (
    get_bulk_reindex,
    get_historic_citations,
    get_internal_reads,
    get_knowledge_portfolio,
    get_nudge_finding_owners,
    get_reinstate_to_corpus,
    get_retire_from_corpus,
    require_service_caller,
)
from smb_requirement_agent.workflows.application.use_cases.internal_reads import (
    CorpusSummary,
    DependentsPage,
    InternalReads,
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
# One page of the library list, with room to spare.
CITATION_COUNTS_MAX = 100
PortfolioDep = Annotated[KnowledgePortfolio, Depends(get_knowledge_portfolio)]
NudgeDep = Annotated[NudgeFindingOwners, Depends(get_nudge_finding_owners)]


class CorpusActionRequest(BaseModel):
    """The knowledge admin acting, and why: recorded with the action and told to the owner."""

    actor_id: str = Field(min_length=1, max_length=200)
    actor_name: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=REASON_MAX)


class ReindexRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=200)
    actor_name: str = Field(min_length=1, max_length=200)
    # "failed": retry every Requirement that stopped indexing; "requirements": index these again.
    scope: Literal["failed", "requirements"]
    requirement_ids: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        default_factory=list, max_length=REINDEX_MAX
    )
    reason: str | None = Field(None, min_length=1, max_length=REASON_MAX)


class NudgeRequest(BaseModel):
    """The knowledge admin who asks: named in the record and in each owner's notification."""

    actor_id: str = Field(min_length=1, max_length=200)
    actor_name: str = Field(min_length=1, max_length=200)


class CitationCounts(BaseModel):
    """Requirements citing each library document now; 0 when none does."""

    counts: dict[str, int]


DocumentIds = Annotated[
    list[Annotated[str, Field(min_length=1, max_length=200)]],
    Query(alias="document_id", min_length=1, max_length=CITATION_COUNTS_MAX),
]


@router.get("/references/citation-counts")
def citation_counts(document_ids: DocumentIds, reads: ReadsDep) -> CitationCounts:
    return CitationCounts(counts=reads.citation_counts(tuple(document_ids)))


# --- Where historic requirements are cited (Knowledge Center E2, ADR-0102) -----------------

HistoricCitationsDep = Annotated[HistoricCitations, Depends(get_historic_citations)]
HistoricIds = Annotated[
    list[Annotated[str, Field(min_length=1, max_length=200)]],
    Query(alias="historic_id", min_length=1, max_length=CITATION_COUNTS_MAX),
]


class HistoricCitationCounts(BaseModel):
    """Requirements whose prior art cites each historic requirement; 0 when none does."""

    counts: dict[str, int]


class HistoricCitationItem(BaseModel):
    requirement_id: str
    title: str
    owner: str
    checked_at: datetime
    # Whether that prior-art check is still current for the Requirement as it stands.
    current: bool
    retired: bool
    duplicate: bool


class HistoricCitationPage(BaseModel):
    items: list[HistoricCitationItem]
    next_offset: int | None


@router.get("/knowledge/historic/citation-counts")
def historic_citation_counts(
    historic_ids: HistoricIds, citations: HistoricCitationsDep
) -> HistoricCitationCounts:
    return HistoricCitationCounts(counts=citations.counts(tuple(historic_ids)))


@router.get("/knowledge/historic/{historic_requirement_id}/citations")
def historic_citations(
    historic_requirement_id: Annotated[str, Path(min_length=1, max_length=200)],
    citations: HistoricCitationsDep,
    offset: int = Query(0, ge=0, le=100_000),
    limit: int = Query(20, ge=1, le=100),
) -> HistoricCitationPage:
    """Requirements citing a historic requirement: who and when, never what was matched."""
    items, next_offset = citations.page(historic_requirement_id, offset, limit)
    return HistoricCitationPage(
        items=[
            HistoricCitationItem(
                requirement_id=item.requirement_id,
                title=item.title,
                owner=item.owner,
                checked_at=item.checked_at,
                current=item.current,
                retired=item.retired,
                duplicate=item.duplicate,
            )
            for item in items
        ],
        next_offset=next_offset,
    )


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


@router.get("/knowledge/corpus")
def knowledge_corpus(
    portfolio: PortfolioDep,
    index_state: IndexState | None = None,
    owner_id: str | None = Query(None, min_length=1, max_length=200),
    q: str = Query("", max_length=200),
    open_findings_only: bool = False,
    not_screened_for_days: int | None = Query(None, ge=1, le=3650),
    retired_only: bool = False,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> CorpusPage:
    """The corpus Requirement by Requirement: identity and state, never content."""
    return portfolio.corpus(
        index_state=index_state,
        owner_id=owner_id,
        text=q,
        open_findings_only=open_findings_only,
        not_screened_for_days=not_screened_for_days,
        offset=offset,
        limit=limit,
        retired_only=retired_only,
    )


@router.get("/knowledge/findings")
def knowledge_findings(
    portfolio: PortfolioDep,
    kind: KnowledgeRelationshipKind | None = None,
    age: FindingAge | None = None,
    owner_id: str | None = Query(None, min_length=1, max_length=200),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> FindingsPage:
    """Findings in force across the corpus, the longest-standing first."""
    return portfolio.findings(kind=kind, age=age, owner_id=owner_id, offset=offset, limit=limit)


@router.post("/knowledge/findings/{finding_id}/nudge")
def nudge_finding_owners(finding_id: str, body: NudgeRequest, nudge: NudgeDep) -> NudgeResult:
    """Ask both Requirements' owners to decide a finding; at most once a week."""
    return nudge.execute(finding_id, body.actor_id, body.actor_name)


@router.post("/knowledge/requirements/{requirement_id}/retirement")
def retire_from_corpus(
    requirement_id: str,
    body: CorpusActionRequest,
    retire: Annotated[RetireFromCorpus, Depends(get_retire_from_corpus)],
) -> MembershipResult:
    """Take a Requirement out of the corpus; every open finding citing it closes."""
    return retire.execute(requirement_id, body.actor_id, body.actor_name, body.reason)


@router.post("/knowledge/requirements/{requirement_id}/reinstatement")
def reinstate_to_corpus(
    requirement_id: str,
    body: CorpusActionRequest,
    reinstate: Annotated[ReinstateToCorpus, Depends(get_reinstate_to_corpus)],
) -> MembershipResult:
    """Return a retired Requirement to the corpus; it is indexed again and screened afresh."""
    return reinstate.execute(requirement_id, body.actor_id, body.actor_name, body.reason)


@router.post("/knowledge/reindex")
def reindex_corpus(
    body: ReindexRequest,
    bulk: Annotated[BulkReindexRequirements, Depends(get_bulk_reindex)],
) -> BulkResult:
    """Retry what stopped indexing, or index chosen Requirements again; the worker does it."""
    if body.scope == "failed":
        return bulk.retry_failed(body.actor_id, body.actor_name, body.reason)
    return bulk.reindex(tuple(body.requirement_ids), body.actor_id, body.actor_name, body.reason)


def contract_openapi() -> dict[str, Any]:
    """This internal API on its own: the contract the knowledge service builds against."""
    application = FastAPI(title="Requirement service internal API")
    application.include_router(router)
    return application.openapi()
