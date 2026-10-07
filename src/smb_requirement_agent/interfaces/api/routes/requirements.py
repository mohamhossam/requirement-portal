"""Requirements API routes.

Maps HTTP requests to application use cases.  Domain and application errors are
translated to status codes centrally in ``interfaces.api.error_handlers``.
No business logic lives here.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from smb_requirement_agent.application.ports.requirement_worklist import (
    WorkflowStatus,
    WorklistSort,
)
from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirementInput
from smb_requirement_agent.application.use_cases.documents import ListDocuments
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.application.use_cases.get_requirement import GetRequirement
from smb_requirement_agent.application.use_cases.owned_requirements import (
    CreateOwnedRequirement,
    CreateOwnedRequirementDraft,
    GetOwnedRequirementDraft,
    ListOwnedRequirementDrafts,
    PromoteOwnedRequirementDraft,
    SaveOwnedRequirementDraft,
)
from smb_requirement_agent.application.use_cases.requirement_drafts import (
    RequirementDraftInput,
)
from smb_requirement_agent.application.use_cases.requirement_impact import (
    PreviewRequirementImpact,
    RequirementImpactPreview,
    UpdateRequirementWithImpact,
)
from smb_requirement_agent.application.use_cases.requirement_worklist import (
    RequirementWorklistItem,
    RequirementWorklistQuery,
    RequirementWorklistReader,
)
from smb_requirement_agent.application.use_cases.update_requirement import (
    UpdateRequirementInput,
)
from smb_requirement_agent.domain.requirement.entities import Requirement, RequirementDraft
from smb_requirement_agent.domain.requirement.value_objects import RequirementContext
from smb_requirement_agent.domain.shared.actors import ActorId
from smb_requirement_agent.domain.shared.identifiers import RequirementId
from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    RequirementCommandsDep,
    get_create_requirement,
    get_create_requirement_draft,
    get_generation_context_tokens,
    get_get_requirement,
    get_get_requirement_draft,
    get_list_documents,
    get_list_requirement_drafts,
    get_list_requirement_worklist,
    get_preview_requirement_impact,
    get_promote_requirement_draft,
    get_save_requirement_draft,
    get_update_requirement,
    limit_provider_calls,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.routes.identity import actor_response
from smb_requirement_agent.interfaces.api.schemas.requirements import (
    AnalysisEligibilityResponse,
    ArtifactCountsResponse,
    CreateRequirementRequest,
    LastActivityResponse,
    OwnerFacetResponse,
    PromoteRequirementDraftRequest,
    RequirementDraftRequest,
    RequirementDraftResponse,
    RequirementImpactResponse,
    RequirementListResponse,
    RequirementResponse,
    RequirementWorklistItemResponse,
    SaveRequirementDraftRequest,
    UpdateRequirementRequest,
    WorkflowStatusCountsResponse,
)

router = APIRouter(
    prefix="/requirements",
    tags=["requirements"],
    dependencies=[Depends(require_authenticated_actor)],
)


def _to_response(
    requirement: Requirement,
    documents: ListDocuments,
    generation_context: GenerationContextTokens | None = None,
) -> RequirementResponse:
    eligibility = documents.eligibility(requirement)
    return RequirementResponse(
        id=requirement.id.value,
        title=requirement.title.value,
        description=requirement.description.value,
        status=requirement.status,
        duplicate_of_requirement_id=(
            requirement.duplicate_of_requirement_id.value
            if requirement.duplicate_of_requirement_id
            else None
        ),
        desired_outcome=_context(requirement.desired_outcome),
        customer_context=_context(requirement.customer_context),
        channels=[item.value for item in requirement.channels],
        systems=[item.value for item in requirement.systems],
        business_rules=[item.value for item in requirement.business_rules],
        constraints=[item.value for item in requirement.constraints],
        version=requirement.version.value,
        updated_at=requirement.updated_at,
        analysis_eligibility=AnalysisEligibilityResponse(
            eligible=eligibility.eligible,
            missing_fields=list(eligibility.missing_fields),
        ),
        analysis_context_token=(
            generation_context.analysis_for(requirement) if generation_context else None
        ),
    )


def _draft_to_response(
    draft: RequirementDraft, documents: ListDocuments
) -> RequirementDraftResponse:
    eligibility = documents.eligibility(draft)
    return RequirementDraftResponse(
        id=draft.id.value,
        title=draft.title,
        description=draft.description,
        desired_outcome=draft.desired_outcome,
        customer_context=draft.customer_context,
        channels=list(draft.channels),
        systems=list(draft.systems),
        business_rules=list(draft.business_rules),
        constraints=list(draft.constraints),
        version=draft.version.value,
        updated_at=draft.updated_at,
        analysis_eligibility=AnalysisEligibilityResponse(
            eligible=eligibility.eligible,
            missing_fields=list(eligibility.missing_fields),
        ),
    )


def _impact_to_response(impact: RequirementImpactPreview) -> RequirementImpactResponse:
    return RequirementImpactResponse(
        requirement_id=impact.requirement_id.value,
        requirement_version=impact.requirement_version,
        analysis_count=impact.analysis_count,
        epic_count=impact.epic_count,
        feature_count=impact.feature_count,
        story_count=impact.story_count,
        source_changed=impact.source_changed,
        requires_acknowledgement=impact.requires_acknowledgement,
    )


def _context(value: RequirementContext | None) -> str | None:
    return value.value if value is not None else None


def _draft_input(body: RequirementDraftRequest) -> RequirementDraftInput:
    return RequirementDraftInput(
        title=body.title,
        description=body.description,
        desired_outcome=body.desired_outcome,
        customer_context=body.customer_context,
        channels=tuple(body.channels),
        systems=tuple(body.systems),
        business_rules=tuple(body.business_rules),
        constraints=tuple(body.constraints),
    )


def _update_input(body: UpdateRequirementRequest) -> UpdateRequirementInput:
    return UpdateRequirementInput(
        title=body.title,
        description=body.description,
        desired_outcome=body.desired_outcome,
        customer_context=body.customer_context,
        channels=None if body.channels is None else tuple(body.channels),
        systems=None if body.systems is None else tuple(body.systems),
        business_rules=None if body.business_rules is None else tuple(body.business_rules),
        constraints=None if body.constraints is None else tuple(body.constraints),
        expected_version=body.expected_version,
    )


def _to_worklist_response(
    item: RequirementWorklistItem, documents: ListDocuments
) -> RequirementWorklistItemResponse:
    requirement = item.snapshot.requirement
    return RequirementWorklistItemResponse(
        id=requirement.id.value,
        title=requirement.title.value,
        description=requirement.description.value,
        status=requirement.status,
        desired_outcome=_context(requirement.desired_outcome),
        customer_context=_context(requirement.customer_context),
        channels=[value.value for value in requirement.channels],
        systems=[value.value for value in requirement.systems],
        business_rules=[value.value for value in requirement.business_rules],
        constraints=[value.value for value in requirement.constraints],
        version=requirement.version.value,
        analysis_eligibility=AnalysisEligibilityResponse(
            eligible=documents.eligibility(requirement).eligible,
            missing_fields=list(documents.eligibility(requirement).missing_fields),
        ),
        workflow_status=item.workflow_status,
        current_stage=item.current_stage,
        next_action=item.next_action,
        answered_items=item.answered_items,
        unresolved_items=item.unresolved_items,
        stale_items=item.stale_items,
        artifact_counts=ArtifactCountsResponse(
            epics=item.artifact_counts.epics,
            features=item.artifact_counts.features,
            stories=item.artifact_counts.stories,
        ),
        updated_at=item.snapshot.updated_at,
        owner=actor_response(item.owner) if item.owner is not None else None,
        reviewer_count=item.reviewer_count,
        active_ai_operation=item.snapshot.active_ai_operation,
        last_activity=(
            LastActivityResponse(
                action=item.last_activity.action.value,
                occurred_at=item.last_activity.occurred_at,
                actor=(
                    actor_response(item.last_activity.actor)
                    if item.last_activity.actor is not None
                    else None
                ),
            )
            if item.last_activity is not None
            else None
        ),
    )


@router.post(
    "",
    response_model=RequirementResponse,
    status_code=201,
    dependencies=[Depends(limit_provider_calls)],
)
def create_requirement(
    documents: Annotated[ListDocuments, Depends(get_list_documents)],
    body: CreateRequirementRequest,
    actor: CurrentActorDep,
    use_case: Annotated[CreateOwnedRequirement, Depends(get_create_requirement)],
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
) -> RequirementResponse:
    requirement = use_case.execute(
        CreateRequirementInput(
            title=body.title,
            description=body.description,
            desired_outcome=body.desired_outcome,
            customer_context=body.customer_context,
            channels=tuple(body.channels),
            systems=tuple(body.systems),
            business_rules=tuple(body.business_rules),
            constraints=tuple(body.constraints),
        ),
        actor,
    )
    return _to_response(requirement, documents, generation_context)


@router.get("", response_model=RequirementListResponse)
def list_requirements(
    documents: Annotated[ListDocuments, Depends(get_list_documents)],
    use_case: Annotated[RequirementWorklistReader, Depends(get_list_requirement_worklist)],
    actor: CurrentActorDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    workflow_status: Annotated[list[WorkflowStatus] | None, Query()] = None,
    sort: WorklistSort = WorklistSort.UPDATED_DESC,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    owner_id: str | None = None,
    assigned_to_me: bool = False,
) -> RequirementListResponse:
    result = use_case.execute(
        RequirementWorklistQuery(
            q=q,
            workflow_statuses=frozenset(workflow_status or []),
            sort=sort,
            offset=offset,
            limit=limit,
            owner_id=ActorId(owner_id) if owner_id else None,
            assigned_to_me=assigned_to_me,
            current_actor_id=actor.id,
        )
    )
    return RequirementListResponse(
        requirements=[_to_worklist_response(item, documents) for item in result.requirements],
        attention=[_to_worklist_response(item, documents) for item in result.attention],
        total=result.total,
        offset=result.offset,
        limit=result.limit,
        has_more=result.has_more,
        status_counts=WorkflowStatusCountsResponse(
            **{status.value: count for status, count in result.status_counts.items()}
        ),
        owner_facets=[
            OwnerFacetResponse(actor=actor_response(item.actor), count=item.count)
            for item in result.owner_facets
        ],
    )


@router.post("/drafts", response_model=RequirementDraftResponse, status_code=201)
def create_requirement_draft(
    documents: Annotated[ListDocuments, Depends(get_list_documents)],
    body: RequirementDraftRequest,
    actor: CurrentActorDep,
    use_case: Annotated[CreateOwnedRequirementDraft, Depends(get_create_requirement_draft)],
) -> RequirementDraftResponse:
    return _draft_to_response(use_case.execute(_draft_input(body), actor), documents)


@router.get("/drafts", response_model=list[RequirementDraftResponse])
def list_requirement_drafts(
    documents: Annotated[ListDocuments, Depends(get_list_documents)],
    actor: CurrentActorDep,
    use_case: Annotated[ListOwnedRequirementDrafts, Depends(get_list_requirement_drafts)],
    unowned: bool = False,
) -> list[RequirementDraftResponse]:
    return [
        _draft_to_response(draft, documents) for draft in use_case.execute(actor, unowned=unowned)
    ]


@router.get("/drafts/{draft_id}", response_model=RequirementDraftResponse)
def get_requirement_draft(
    documents: Annotated[ListDocuments, Depends(get_list_documents)],
    draft_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[GetOwnedRequirementDraft, Depends(get_get_requirement_draft)],
) -> RequirementDraftResponse:
    return _draft_to_response(use_case.execute(RequirementId(draft_id), actor), documents)


@router.put("/drafts/{draft_id}", response_model=RequirementDraftResponse)
def save_requirement_draft(
    documents: Annotated[ListDocuments, Depends(get_list_documents)],
    draft_id: str,
    body: SaveRequirementDraftRequest,
    actor: CurrentActorDep,
    use_case: Annotated[SaveOwnedRequirementDraft, Depends(get_save_requirement_draft)],
) -> RequirementDraftResponse:
    return _draft_to_response(
        use_case.execute(RequirementId(draft_id), _draft_input(body), body.expected_version, actor),
        documents,
    )


@router.post(
    "/drafts/{draft_id}/promote",
    response_model=RequirementResponse,
    status_code=201,
    dependencies=[Depends(limit_provider_calls)],
)
def promote_requirement_draft(
    documents: Annotated[ListDocuments, Depends(get_list_documents)],
    draft_id: str,
    body: PromoteRequirementDraftRequest,
    actor: CurrentActorDep,
    use_case: Annotated[PromoteOwnedRequirementDraft, Depends(get_promote_requirement_draft)],
) -> RequirementResponse:
    return _to_response(
        use_case.execute(RequirementId(draft_id), body.expected_version, actor), documents
    )


@router.get("/{requirement_id}", response_model=RequirementResponse)
def get_requirement(
    documents: Annotated[ListDocuments, Depends(get_list_documents)],
    requirement_id: str,
    use_case: Annotated[GetRequirement, Depends(get_get_requirement)],
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
    commands: RequirementCommandsDep,
) -> RequirementResponse:
    resolved = RequirementId(requirement_id)
    return commands.read(
        resolved,
        lambda: _to_response(use_case.execute(resolved), documents, generation_context),
    )


@router.put(
    "/{requirement_id}",
    response_model=RequirementResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def update_requirement(
    documents: Annotated[ListDocuments, Depends(get_list_documents)],
    requirement_id: str,
    body: UpdateRequirementRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[UpdateRequirementWithImpact, Depends(get_update_requirement)],
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
) -> RequirementResponse:
    resolved = RequirementId(requirement_id)
    return commands.run_and_present(
        resolved,
        actor,
        lambda: use_case.execute(
            actor,
            resolved,
            _update_input(body),
            impact_acknowledged=body.impact_acknowledged,
        ),
        lambda requirement: _to_response(requirement, documents, generation_context),
    )


@router.post("/{requirement_id}/impact-preview", response_model=RequirementImpactResponse)
def preview_requirement_impact(
    requirement_id: str,
    body: UpdateRequirementRequest,
    use_case: Annotated[PreviewRequirementImpact, Depends(get_preview_requirement_impact)],
) -> RequirementImpactResponse:
    return _impact_to_response(use_case.execute(RequirementId(requirement_id), _update_input(body)))
