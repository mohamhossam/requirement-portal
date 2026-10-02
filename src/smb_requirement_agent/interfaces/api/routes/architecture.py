"""Whole-breakdown architecture mapping endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from smb_requirement_agent.application.use_cases.architecture_mapping import (
    MapBreakdownArchitecture,
)
from smb_requirement_agent.application.use_cases.architecture_mapping_jobs import (
    ArchitectureMappingJobs,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    KnowledgeActorDep,
    get_architecture_mapping_jobs,
    get_map_breakdown_architecture,
    limit_provider_calls,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.schemas.architecture import (
    ArchitectureImpactResponse,
    BreakdownArchitectureMappingResponse,
    FeatureArchitectureMappingResponse,
    StoryArchitectureMappingResponse,
)
from smb_requirement_agent.interfaces.api.schemas.architecture_knowledge import (
    ArchitectureJobResponse,
)

router = APIRouter(
    prefix="/requirements",
    tags=["architecture"],
    dependencies=[Depends(require_authenticated_actor)],
)


@router.post(
    "/{requirement_id}/architecture-mapping/jobs",
    response_model=ArchitectureJobResponse,
    status_code=202,
    dependencies=[Depends(limit_provider_calls)],
)
def start_mapping_job(
    requirement_id: str,
    actor: KnowledgeActorDep,
    jobs: Annotated[ArchitectureMappingJobs, Depends(get_architecture_mapping_jobs)],
) -> ArchitectureJobResponse:
    return ArchitectureJobResponse.from_domain(jobs.start(RequirementId(requirement_id), actor))


@router.post(
    "/{requirement_id}/architecture-mapping",
    response_model=BreakdownArchitectureMappingResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def map_architecture(
    requirement_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[MapBreakdownArchitecture, Depends(get_map_breakdown_architecture)],
) -> BreakdownArchitectureMappingResponse:
    result = use_case.execute(actor, RequirementId(requirement_id))
    return BreakdownArchitectureMappingResponse(
        requirement_id=result.requirement_id.value,
        features=[
            FeatureArchitectureMappingResponse(
                feature_id=item.feature.id.value,
                architecture=ArchitectureImpactResponse.from_domain(item.impact),
                stories=[
                    StoryArchitectureMappingResponse(
                        story_id=story.story.id.value,
                        architecture=ArchitectureImpactResponse.from_domain(story.impact),
                    )
                    for story in item.stories
                ],
            )
            for item in result.features
        ],
    )
