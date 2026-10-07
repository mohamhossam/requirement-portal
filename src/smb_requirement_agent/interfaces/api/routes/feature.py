"""Feature API routes.

Domain and application errors are translated to status codes centrally in
``interfaces.api.error_handlers``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from smb_requirement_agent.application.use_cases.approval_policy import artifact_fingerprint
from smb_requirement_agent.application.use_cases.feature_review import (
    ApproveFeature,
    EditFeature,
    EditFeatureInput,
    GetFeatures,
)
from smb_requirement_agent.application.use_cases.generate_features import (
    GenerateFeatures,
    GenerateFeaturesResult,
)
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.application.use_cases.requirement_commands import ExpectedContext
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.shared.identifiers import RequirementId
from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    RequirementCommandsDep,
    get_approve_feature,
    get_edit_feature,
    get_generate_features,
    get_generation_context_tokens,
    get_get_features,
    limit_provider_calls,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.schemas.architecture import ArchitectureImpactResponse
from smb_requirement_agent.interfaces.api.schemas.epic import ProvenanceResponse, StalenessResponse
from smb_requirement_agent.interfaces.api.schemas.feature import (
    EditFeatureRequest,
    FeatureActionsResponse,
    FeatureResponse,
    FeatureSetResponse,
)
from smb_requirement_agent.interfaces.api.schemas.generation import (
    ActionAvailabilityResponse,
    GenerationRequest,
)
from smb_requirement_agent.interfaces.api.schemas.governance import (
    ApprovalRequest,
    ApprovalResponse,
)

router = APIRouter(
    prefix="/requirements", tags=["features"], dependencies=[Depends(require_authenticated_actor)]
)


def _to_response(feature: Feature, story_context_token: str | None = None) -> FeatureResponse:
    fingerprint = artifact_fingerprint(feature)
    current = feature.current_approval(fingerprint)
    return FeatureResponse(
        id=feature.id.value,
        version=feature.version,
        epic_id=feature.epic_id.value,
        name=feature.name.value,
        outcome=feature.outcome.value,
        delivery_drop=feature.delivery_drop,
        splitting_pattern=feature.splitting_pattern,
        splitting_rationale=feature.splitting_rationale.value,
        status=feature.status,
        provenance=ProvenanceResponse(
            generated_at=feature.provenance.generated_at,
            model=feature.provenance.model,
            prompt_version=feature.provenance.prompt_version,
        ),
        stale=(
            StalenessResponse(reason=feature.staleness.reason, since=feature.staleness.since)
            if feature.staleness is not None
            else None
        ),
        architecture=(
            ArchitectureImpactResponse.from_domain(feature.architecture)
            if feature.architecture is not None
            else None
        ),
        content_fingerprint=fingerprint,
        current_approval=ApprovalResponse.from_domain(current) if current else None,
        approval_history=[ApprovalResponse.from_domain(item) for item in feature.approvals],
        actions=FeatureActionsResponse(
            approve=ActionAvailabilityResponse.from_domain(feature.approval_availability()),
            generate_stories=ActionAvailabilityResponse.from_domain(feature.story_availability()),
        ),
        story_context_token=story_context_token,
    )


def _to_set_response(
    requirement_id: RequirementId,
    features: list[Feature],
    generation_context: GenerationContextTokens,
) -> FeatureSetResponse:
    epic_id = features[0].epic_id
    return FeatureSetResponse(
        epic_id=epic_id.value,
        features=[
            _to_response(feature, generation_context.stories(requirement_id, feature.id))
            for feature in features
        ],
        set_version=generation_context.feature_set_version(requirement_id),
        generation_context_token=generation_context.features(requirement_id),
    )


@router.post(
    "/{requirement_id}/features",
    response_model=FeatureSetResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def generate_features(
    requirement_id: str,
    body: GenerationRequest,
    actor: CurrentActorDep,
    response: Response,
    commands: RequirementCommandsDep,
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
    use_case: Annotated[GenerateFeatures, Depends(get_generate_features)],
) -> FeatureSetResponse:
    """Decompose the approved Epic. 201 on first generation, 200 when replaced."""
    resolved = RequirementId(requirement_id)

    def present(result: GenerateFeaturesResult) -> FeatureSetResponse:
        response.status_code = 200 if result.replaced_existing else 201
        return _to_set_response(resolved, result.features, generation_context)

    return commands.run_and_present(
        resolved,
        actor,
        lambda: use_case.execute(actor, resolved, force=body.force),
        present,
        expected=ExpectedContext(body.context_token, lambda: generation_context.features(resolved)),
    )


@router.get("/{requirement_id}/features", response_model=FeatureSetResponse)
def get_features(
    requirement_id: str,
    commands: RequirementCommandsDep,
    use_case: Annotated[GetFeatures, Depends(get_get_features)],
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
) -> FeatureSetResponse:
    resolved = RequirementId(requirement_id)
    return commands.read(
        resolved,
        lambda: _to_set_response(resolved, use_case.execute(resolved), generation_context),
    )


@router.put("/{requirement_id}/features/{feature_id}", response_model=FeatureResponse)
def edit_feature(
    requirement_id: str,
    feature_id: str,
    body: EditFeatureRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[EditFeature, Depends(get_edit_feature)],
) -> FeatureResponse:
    resolved = RequirementId(requirement_id)
    edit = EditFeatureInput(
        name=body.name,
        outcome=body.outcome,
        delivery_drop=body.delivery_drop.value,
        splitting_pattern=body.splitting_pattern.value,
        splitting_rationale=body.splitting_rationale,
        source_reconciled=body.source_reconciled,
        expected_version=body.expected_version,
    )
    return _to_response(
        commands.run(
            resolved, actor, lambda: use_case.execute(actor, resolved, FeatureId(feature_id), edit)
        )
    )


@router.post("/{requirement_id}/features/{feature_id}/approval", response_model=FeatureResponse)
def approve_feature(
    requirement_id: str,
    feature_id: str,
    body: ApprovalRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[ApproveFeature, Depends(get_approve_feature)],
) -> FeatureResponse:
    resolved = RequirementId(requirement_id)
    return _to_response(
        commands.run(
            resolved,
            actor,
            lambda: use_case.execute(
                resolved,
                FeatureId(feature_id),
                actor,
                body.expected_version,
                body.expected_content_fingerprint,
                body.rationale,
            ),
        )
    )
