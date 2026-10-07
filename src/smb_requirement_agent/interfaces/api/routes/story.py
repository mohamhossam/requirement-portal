"""Feature-scoped User Story API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from smb_requirement_agent.application.use_cases.approval_policy import artifact_fingerprint
from smb_requirement_agent.application.use_cases.approval_workflow import ApproveStory, RejectStory
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.application.use_cases.requirement_commands import ExpectedContext
from smb_requirement_agent.application.use_cases.story_change_proposals import StoryChangeProposals
from smb_requirement_agent.application.use_cases.story_quality import (
    GetFeatureQualitySnapshot,
    SuggestStorySplit,
    ValidateFeatureStories,
    ValidateStory,
)
from smb_requirement_agent.application.use_cases.story_workflow import (
    AcceptanceCriterionInput,
    EditStory,
    GenerateStories,
    GetStories,
    MergeStories,
    RegenerateStory,
    SplitStory,
    StoryInput,
)
from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.story.entities import StoryChangeProposal, StoryDraft, UserStory
from smb_requirement_agent.domain.story.quality import InvestAssessment, SpidrRecommendation
from smb_requirement_agent.domain.story.value_objects import StoryId, StoryProposalId
from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    RequirementCommandsDep,
    get_approve_story,
    get_edit_story,
    get_feature_quality_snapshot,
    get_generate_stories,
    get_generation_context_tokens,
    get_get_stories,
    get_merge_stories,
    get_regenerate_story,
    get_reject_story,
    get_split_story,
    get_story_change_proposals,
    get_suggest_story_split,
    get_validate_feature_stories,
    get_validate_story,
    limit_provider_calls,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.schemas.architecture import ArchitectureImpactResponse
from smb_requirement_agent.interfaces.api.schemas.epic import ProvenanceResponse, StalenessResponse
from smb_requirement_agent.interfaces.api.schemas.generation import (
    ActionAvailabilityResponse,
    GenerationRequest,
)
from smb_requirement_agent.interfaces.api.schemas.governance import (
    ApprovalRequest,
    ApprovalResponse,
    StoryRejectionRequest,
)
from smb_requirement_agent.interfaces.api.schemas.story import (
    AcceptanceCriterionPayload,
    FeatureStoryQualityResponse,
    FeatureStoryQualitySnapshotResponse,
    MergeStoriesRequest,
    SpidrRecommendationResponse,
    SplitStoryRequest,
    StoryActionsResponse,
    StoryChangeProposalRequest,
    StoryChangeProposalResponse,
    StoryContentRequest,
    StoryDraftRequest,
    StoryProposalCandidateResponse,
    StoryProposalMutationRequest,
    StoryQualityResponse,
    StoryResponse,
    StorySetResponse,
    ValidationFindingResponse,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

router = APIRouter(
    prefix="/requirements", tags=["stories"], dependencies=[Depends(require_authenticated_actor)]
)


def _input(value: StoryContentRequest) -> StoryInput:
    return StoryInput(
        role=value.role,
        action=value.action,
        value=value.value,
        acceptance_criteria=tuple(
            AcceptanceCriterionInput(item.given, item.when, item.then)
            for item in value.acceptance_criteria
        ),
        source_reconciled=value.source_reconciled,
        expected_version=(value.expected_version if isinstance(value, StoryDraftRequest) else 1),
    )


def _story_response(story: UserStory, context_token: str | None = None) -> StoryResponse:
    fingerprint = artifact_fingerprint(story)
    current = story.current_approval(fingerprint)
    return StoryResponse(
        id=story.id.value,
        version=story.version,
        feature_id=story.feature_id.value,
        role=story.role.value,
        action=story.action.value,
        value=story.value.value,
        voice=story.voice,
        acceptance_criteria=[
            AcceptanceCriterionPayload(given=item.given, when=item.when, then=item.then)
            for item in story.acceptance_criteria
        ],
        status=story.status,
        provenance=ProvenanceResponse(
            generated_at=story.provenance.generated_at,
            model=story.provenance.model,
            prompt_version=story.provenance.prompt_version,
        ),
        stale=StalenessResponse(reason=story.staleness.reason, since=story.staleness.since)
        if story.staleness
        else None,
        architecture=(
            ArchitectureImpactResponse.from_domain(story.architecture)
            if story.architecture is not None
            else None
        ),
        content_fingerprint=fingerprint,
        current_approval=ApprovalResponse.from_domain(current) if current else None,
        approval_history=[ApprovalResponse.from_domain(item) for item in story.approvals],
        actions=StoryActionsResponse(
            approve=ActionAvailabilityResponse.from_domain(story.approval_availability()),
            regenerate=ActionAvailabilityResponse.from_domain(story.regeneration_availability()),
        ),
        story_context_token=context_token,
    )


def _set(
    requirement_id: RequirementId,
    feature_id: FeatureId,
    stories: list[UserStory],
    generation_context: GenerationContextTokens,
) -> StorySetResponse:
    return StorySetResponse(
        feature_id=feature_id.value,
        stories=[
            _story_response(item, generation_context.story(requirement_id, feature_id, item.id))
            for item in stories
        ],
        set_version=generation_context.story_set_version(feature_id),
        generation_context_token=generation_context.stories(requirement_id, feature_id),
    )


def _candidate_response(candidate: StoryDraft) -> StoryProposalCandidateResponse:
    if candidate.provenance is None:
        raise AssertionError("AI proposal candidate must carry provenance.")
    voice = (
        f"As a {candidate.role.value}, I want {candidate.action.value}, "
        f"so that {candidate.value.value}."
    )
    return StoryProposalCandidateResponse(
        role=candidate.role.value,
        action=candidate.action.value,
        value=candidate.value.value,
        voice=voice,
        acceptance_criteria=[
            AcceptanceCriterionPayload(given=item.given, when=item.when, then=item.then)
            for item in candidate.acceptance_criteria
        ],
        provenance=ProvenanceResponse(
            generated_at=candidate.provenance.generated_at,
            model=candidate.provenance.model,
            prompt_version=candidate.provenance.prompt_version,
        ),
    )


def _proposal_response(proposal: StoryChangeProposal) -> StoryChangeProposalResponse:
    candidates: list[StoryProposalCandidateResponse] = []
    assessments = {item.story_id: item for item in proposal.quality_assessments}
    for index, draft in enumerate(proposal.candidates):
        response = _candidate_response(draft)
        if index < len(proposal.prepared_candidates):
            prepared = proposal.prepared_candidates[index]
            assessment = assessments.get(prepared.id)
            if assessment is not None:
                response.quality = _quality_response(
                    assessment, SuggestStorySplit.for_assessment(assessment)
                )
            if prepared.architecture is not None:
                response.architecture = ArchitectureImpactResponse.from_domain(
                    prepared.architecture
                )
        candidates.append(response)
    return StoryChangeProposalResponse(
        id=proposal.id.value,
        version=proposal.version,
        feature_id=proposal.feature_id.value,
        operation=proposal.operation,
        source_story_ids=[item.value for item in proposal.source_story_ids],
        candidates=candidates,
    )


def _quality_response(
    assessment: InvestAssessment,
    recommendations: tuple[SpidrRecommendation, ...],
) -> StoryQualityResponse:
    return StoryQualityResponse(
        story_id=assessment.story_id.value,
        status=assessment.status,
        failure_count=assessment.failure_count,
        findings=[
            ValidationFindingResponse(
                criterion=item.criterion,
                passed=item.passed,
                message=item.message,
                source=item.source,
            )
            for item in assessment.findings
        ],
        recommendations=[
            SpidrRecommendationResponse(pattern=item.pattern, reason=item.reason)
            for item in recommendations
        ],
        provenance=ProvenanceResponse(
            generated_at=assessment.provenance.generated_at,
            model=assessment.provenance.model,
            prompt_version=assessment.provenance.prompt_version,
        ),
    )


@router.get(
    "/{requirement_id}/features/{feature_id}/stories/quality",
    response_model=FeatureStoryQualityResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def validate_feature_story_quality(
    requirement_id: str,
    feature_id: str,
    use_case: Annotated[ValidateFeatureStories, Depends(get_validate_feature_stories)],
) -> FeatureStoryQualityResponse:
    resolved = FeatureId(feature_id)
    assessments = use_case.execute(RequirementId(requirement_id), resolved)
    return FeatureStoryQualityResponse(
        feature_id=resolved.value,
        stories=[
            _quality_response(item, SuggestStorySplit.for_assessment(item)) for item in assessments
        ],
    )


@router.get(
    "/{requirement_id}/features/{feature_id}/stories/quality-assessment",
    response_model=FeatureStoryQualitySnapshotResponse,
)
def get_feature_story_quality_assessment(
    requirement_id: str,
    feature_id: str,
    use_case: Annotated[GetFeatureQualitySnapshot, Depends(get_feature_quality_snapshot)],
) -> FeatureStoryQualitySnapshotResponse:
    view = use_case.execute(RequirementId(requirement_id), FeatureId(feature_id))
    snapshot = view.snapshot
    return FeatureStoryQualitySnapshotResponse(
        feature_id=snapshot.feature_id.value,
        source_fingerprint=snapshot.source_fingerprint,
        generated_at=snapshot.generated_at,
        fresh=view.fresh,
        stories=[
            _quality_response(item, SuggestStorySplit.for_assessment(item))
            for item in snapshot.assessments
        ],
    )


@router.get(
    "/{requirement_id}/features/{feature_id}/stories/{story_id}/quality",
    response_model=StoryQualityResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def validate_story_quality(
    requirement_id: str,
    feature_id: str,
    story_id: str,
    use_case: Annotated[ValidateStory, Depends(get_validate_story)],
) -> StoryQualityResponse:
    assessment = use_case.execute(
        RequirementId(requirement_id), FeatureId(feature_id), StoryId(story_id)
    )
    return _quality_response(assessment, SuggestStorySplit.for_assessment(assessment))


@router.get(
    "/{requirement_id}/features/{feature_id}/stories/{story_id}/quality/split-recommendations",
    response_model=list[SpidrRecommendationResponse],
    dependencies=[Depends(limit_provider_calls)],
)
def suggest_story_split(
    requirement_id: str,
    feature_id: str,
    story_id: str,
    use_case: Annotated[SuggestStorySplit, Depends(get_suggest_story_split)],
) -> list[SpidrRecommendationResponse]:
    return [
        SpidrRecommendationResponse(pattern=item.pattern, reason=item.reason)
        for item in use_case.execute(
            RequirementId(requirement_id), FeatureId(feature_id), StoryId(story_id)
        )
    ]


@router.post(
    "/{requirement_id}/features/{feature_id}/stories",
    response_model=StorySetResponse,
    status_code=201,
    dependencies=[Depends(limit_provider_calls)],
)
def generate_stories(
    requirement_id: str,
    feature_id: str,
    body: GenerationRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
    use_case: Annotated[GenerateStories, Depends(get_generate_stories)],
) -> StorySetResponse:
    requirement = RequirementId(requirement_id)
    resolved = FeatureId(feature_id)
    return commands.run_and_present(
        requirement,
        actor,
        lambda: use_case.execute(actor, requirement, resolved),
        lambda stories: _set(requirement, resolved, stories, generation_context),
        expected=ExpectedContext(
            body.context_token, lambda: generation_context.stories(requirement, resolved)
        ),
    )


@router.get("/{requirement_id}/features/{feature_id}/stories", response_model=StorySetResponse)
def get_stories(
    requirement_id: str,
    feature_id: str,
    commands: RequirementCommandsDep,
    use_case: Annotated[GetStories, Depends(get_get_stories)],
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
) -> StorySetResponse:
    requirement = RequirementId(requirement_id)
    resolved = FeatureId(feature_id)
    return commands.read(
        requirement,
        lambda: _set(
            requirement, resolved, use_case.execute(requirement, resolved), generation_context
        ),
    )


@router.put(
    "/{requirement_id}/features/{feature_id}/stories/{story_id}", response_model=StoryResponse
)
def edit_story(
    requirement_id: str,
    feature_id: str,
    story_id: str,
    body: StoryDraftRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[EditStory, Depends(get_edit_story)],
) -> StoryResponse:
    requirement = RequirementId(requirement_id)
    return _story_response(
        commands.run(
            requirement,
            actor,
            lambda: use_case.execute(
                actor, requirement, FeatureId(feature_id), StoryId(story_id), _input(body)
            ),
        )
    )


@router.post(
    "/{requirement_id}/features/{feature_id}/stories/{story_id}/approval",
    response_model=StoryResponse,
)
def approve_story(
    requirement_id: str,
    feature_id: str,
    story_id: str,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[ApproveStory, Depends(get_approve_story)],
    body: ApprovalRequest,
) -> StoryResponse:
    requirement = RequirementId(requirement_id)
    return _story_response(
        commands.run(
            requirement,
            actor,
            lambda: use_case.execute(
                requirement,
                FeatureId(feature_id),
                StoryId(story_id),
                actor,
                body.expected_version,
                body.expected_content_fingerprint,
                body.rationale,
            ),
        )
    )


@router.post(
    "/{requirement_id}/features/{feature_id}/stories/{story_id}/rejection",
    response_model=StoryResponse,
)
def reject_story(
    requirement_id: str,
    feature_id: str,
    story_id: str,
    body: StoryRejectionRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[RejectStory, Depends(get_reject_story)],
) -> StoryResponse:
    requirement = RequirementId(requirement_id)
    return _story_response(
        commands.run(
            requirement,
            actor,
            lambda: use_case.execute(
                requirement,
                FeatureId(feature_id),
                StoryId(story_id),
                actor,
                body.reason,
                body.expected_fingerprint,
                body.expected_version,
                body.expected_review_version,
            ),
        )
    )


@router.post(
    "/{requirement_id}/features/{feature_id}/stories/{story_id}/split",
    response_model=StorySetResponse,
)
def split_story(
    requirement_id: str,
    feature_id: str,
    story_id: str,
    body: SplitStoryRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[SplitStory, Depends(get_split_story)],
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
) -> StorySetResponse:
    requirement = RequirementId(requirement_id)
    resolved = FeatureId(feature_id)
    return commands.run_and_present(
        requirement,
        actor,
        lambda: use_case.execute(
            actor,
            requirement,
            resolved,
            StoryId(story_id),
            tuple(_input(item) for item in body.replacements),
            body.expected_set_version,
        ),
        lambda stories: _set(requirement, resolved, stories, generation_context),
    )


@router.post(
    "/{requirement_id}/features/{feature_id}/stories/merge", response_model=StorySetResponse
)
def merge_stories(
    requirement_id: str,
    feature_id: str,
    body: MergeStoriesRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[MergeStories, Depends(get_merge_stories)],
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
) -> StorySetResponse:
    requirement = RequirementId(requirement_id)
    resolved = FeatureId(feature_id)
    return commands.run_and_present(
        requirement,
        actor,
        lambda: use_case.execute(
            actor,
            requirement,
            resolved,
            tuple(StoryId(item) for item in body.story_ids),
            _input(body.replacement),
            body.expected_set_version,
        ),
        lambda stories: _set(requirement, resolved, stories, generation_context),
    )


@router.post(
    "/{requirement_id}/features/{feature_id}/stories/regeneration",
    response_model=StorySetResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def regenerate_stories(
    requirement_id: str,
    feature_id: str,
    body: GenerationRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
    use_case: Annotated[RegenerateStory, Depends(get_regenerate_story)],
) -> StorySetResponse:
    requirement = RequirementId(requirement_id)
    resolved = FeatureId(feature_id)
    return commands.run_and_present(
        requirement,
        actor,
        lambda: use_case.execute_all(actor, requirement, resolved, force=body.force),
        lambda stories: _set(requirement, resolved, stories, generation_context),
        expected=ExpectedContext(
            body.context_token, lambda: generation_context.stories(requirement, resolved)
        ),
    )


@router.post(
    "/{requirement_id}/features/{feature_id}/stories/{story_id}/regeneration",
    response_model=StorySetResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def regenerate_story(
    requirement_id: str,
    feature_id: str,
    story_id: str,
    body: GenerationRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
    use_case: Annotated[RegenerateStory, Depends(get_regenerate_story)],
) -> StorySetResponse:
    requirement = RequirementId(requirement_id)
    resolved = FeatureId(feature_id)
    story = StoryId(story_id)
    return commands.run_and_present(
        requirement,
        actor,
        lambda: use_case.execute_one(actor, requirement, resolved, story, force=body.force),
        lambda stories: _set(requirement, resolved, stories, generation_context),
        expected=ExpectedContext(
            body.context_token, lambda: generation_context.story(requirement, resolved, story)
        ),
    )


@router.post(
    "/{requirement_id}/features/{feature_id}/stories/change-proposals",
    response_model=StoryChangeProposalResponse,
    status_code=201,
    dependencies=[Depends(limit_provider_calls)],
)
def create_story_proposal(
    requirement_id: str,
    feature_id: str,
    body: StoryChangeProposalRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
    use_case: Annotated[StoryChangeProposals, Depends(get_story_change_proposals)],
) -> StoryChangeProposalResponse:
    requirement = RequirementId(requirement_id)
    resolved = FeatureId(feature_id)
    return commands.run_and_present(
        requirement,
        actor,
        lambda: use_case.create(
            actor,
            requirement,
            resolved,
            body.operation,
            tuple(StoryId(item) for item in body.source_story_ids),
        ),
        _proposal_response,
        expected=ExpectedContext(
            body.context_token, lambda: generation_context.stories(requirement, resolved)
        ),
    )


@router.get(
    "/{requirement_id}/features/{feature_id}/stories/change-proposals",
    response_model=list[StoryChangeProposalResponse],
)
def list_story_proposals(
    requirement_id: str,
    feature_id: str,
    use_case: Annotated[StoryChangeProposals, Depends(get_story_change_proposals)],
) -> list[StoryChangeProposalResponse]:
    return [
        _proposal_response(item)
        for item in use_case.list_proposals(RequirementId(requirement_id), FeatureId(feature_id))
    ]


@router.post(
    "/{requirement_id}/features/{feature_id}/stories/change-proposals/{proposal_id}/application",
    response_model=StorySetResponse,
)
def apply_story_proposal(
    requirement_id: str,
    feature_id: str,
    proposal_id: str,
    body: StoryProposalMutationRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[StoryChangeProposals, Depends(get_story_change_proposals)],
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
) -> StorySetResponse:
    requirement = RequirementId(requirement_id)
    resolved = FeatureId(feature_id)
    return commands.run_and_present(
        requirement,
        actor,
        lambda: use_case.apply(
            actor,
            requirement,
            resolved,
            StoryProposalId(proposal_id),
            body.expected_version,
            body.expected_set_version,
        ),
        lambda stories: _set(requirement, resolved, stories, generation_context),
    )


@router.delete(
    "/{requirement_id}/features/{feature_id}/stories/change-proposals/{proposal_id}",
    status_code=204,
)
def discard_story_proposal(
    requirement_id: str,
    feature_id: str,
    proposal_id: str,
    body: StoryProposalMutationRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[StoryChangeProposals, Depends(get_story_change_proposals)],
) -> Response:
    requirement = RequirementId(requirement_id)
    commands.run(
        requirement,
        actor,
        lambda: use_case.discard(
            actor,
            requirement,
            FeatureId(feature_id),
            StoryProposalId(proposal_id),
            body.expected_version,
            body.expected_set_version,
        ),
    )
    return Response(status_code=204)
