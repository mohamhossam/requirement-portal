"""Epic API routes.

Domain and application errors are translated to status codes centrally in
``interfaces.api.error_handlers``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from smb_requirement_agent.breakdown.application.use_cases.edit_epic import EditEpic, EditEpicInput
from smb_requirement_agent.breakdown.application.use_cases.get_epic import GetEpic
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.governance.application.use_cases.approve_epic import ApproveEpic
from smb_requirement_agent.governance.domain.review.fingerprints import artifact_fingerprint
from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    RequirementCommandsDep,
    get_approve_epic,
    get_edit_epic,
    get_generation_context_tokens,
    get_get_epic,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.schemas.epic import (
    EditEpicRequest,
    EpicActionsResponse,
    EpicResponse,
    ProvenanceResponse,
    StalenessResponse,
)
from smb_requirement_agent.interfaces.api.schemas.generation import (
    ActionAvailabilityResponse,
)
from smb_requirement_agent.interfaces.api.schemas.governance import (
    ApprovalRequest,
    ApprovalResponse,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.workflows.application.use_cases.generation_context import (
    GenerationContextTokens,
)

router = APIRouter(
    prefix="/requirements", tags=["epic"], dependencies=[Depends(require_authenticated_actor)]
)


def _to_response(epic: Epic, feature_context_token: str | None = None) -> EpicResponse:
    fingerprint = artifact_fingerprint(epic)
    current = epic.current_approval(fingerprint)
    return EpicResponse(
        id=epic.id.value,
        version=epic.version,
        requirement_id=epic.requirement_id.value,
        name=epic.name.value,
        outcome=epic.outcome.value,
        business_case=epic.business_case.value,
        status=epic.status,
        provenance=ProvenanceResponse(
            generated_at=epic.provenance.generated_at,
            model=epic.provenance.model,
            prompt_version=epic.provenance.prompt_version,
        ),
        stale=(
            StalenessResponse(reason=epic.staleness.reason, since=epic.staleness.since)
            if epic.staleness is not None
            else None
        ),
        content_fingerprint=fingerprint,
        current_approval=ApprovalResponse.from_domain(current) if current else None,
        approval_history=[ApprovalResponse.from_domain(item) for item in epic.approvals],
        actions=EpicActionsResponse(
            approve=ActionAvailabilityResponse.from_domain(epic.approval_availability()),
            regenerate=ActionAvailabilityResponse.from_domain(epic.regeneration_availability()),
            generate_features=ActionAvailabilityResponse.from_domain(
                epic.decomposition_availability()
            ),
        ),
        feature_context_token=feature_context_token,
    )


@router.get("/{requirement_id}/epic", response_model=EpicResponse)
def get_epic(
    requirement_id: str,
    commands: RequirementCommandsDep,
    use_case: Annotated[GetEpic, Depends(get_get_epic)],
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
) -> EpicResponse:
    resolved = RequirementId(requirement_id)
    return commands.read(
        resolved,
        lambda: _to_response(use_case.execute(resolved), generation_context.features(resolved)),
    )


@router.put("/{requirement_id}/epic", response_model=EpicResponse)
def edit_epic(
    requirement_id: str,
    body: EditEpicRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[EditEpic, Depends(get_edit_epic)],
) -> EpicResponse:
    resolved = RequirementId(requirement_id)
    edit = EditEpicInput(
        name=body.name,
        outcome=body.outcome,
        business_case=body.business_case,
        source_reconciled=body.source_reconciled,
        expected_version=body.expected_version,
    )
    return _to_response(
        commands.run(resolved, actor, lambda: use_case.execute(actor, resolved, edit))
    )


@router.post("/{requirement_id}/epic/approval", response_model=EpicResponse)
def approve_epic(
    requirement_id: str,
    body: ApprovalRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[ApproveEpic, Depends(get_approve_epic)],
) -> EpicResponse:
    """Approval is a subresource so a replayed edit payload cannot approve by accident."""
    resolved = RequirementId(requirement_id)
    return _to_response(
        commands.run(
            resolved,
            actor,
            lambda: use_case.execute(
                resolved,
                actor,
                body.expected_version,
                body.expected_content_fingerprint,
                body.rationale,
            ),
        )
    )
