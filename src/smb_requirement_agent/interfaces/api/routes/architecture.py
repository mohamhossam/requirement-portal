"""Whole-breakdown architecture mapping endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from smb_requirement_agent.breakdown.application.errors import ArchitectureJobNotFoundError
from smb_requirement_agent.breakdown.application.ports.architecture_jobs import ArchitectureJob
from smb_requirement_agent.breakdown.application.use_cases.architecture_mapping import (
    MapBreakdownArchitecture,
)
from smb_requirement_agent.breakdown.application.use_cases.architecture_mapping_jobs import (
    ArchitectureMappingJobs,
)
from smb_requirement_agent.identity.application.ports.identity import Actor
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
    ArchitectureJobResponse,
    BreakdownArchitectureMappingResponse,
    FeatureArchitectureMappingResponse,
    StoryArchitectureMappingResponse,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

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


# Mapping jobs are requirement work with their own queue (ADR-0099); the catalogue's
# `/jobs/{id}` routes left with the catalogue.
MappingJobsDep = Annotated[ArchitectureMappingJobs, Depends(get_architecture_mapping_jobs)]


@router.get(
    "/{requirement_id}/architecture-mapping/jobs/{job_id}", response_model=ArchitectureJobResponse
)
def get_mapping_job(
    requirement_id: str, job_id: str, jobs: MappingJobsDep, actor: KnowledgeActorDep
) -> ArchitectureJobResponse:
    return ArchitectureJobResponse.from_domain(
        _requirement_job(requirement_id, job_id, jobs, actor)
    )


@router.post(
    "/{requirement_id}/architecture-mapping/jobs/{job_id}/cancel",
    response_model=ArchitectureJobResponse,
)
def cancel_mapping_job(
    requirement_id: str, job_id: str, jobs: MappingJobsDep, actor: KnowledgeActorDep
) -> ArchitectureJobResponse:
    _requirement_job(requirement_id, job_id, jobs, actor)
    return ArchitectureJobResponse.from_domain(jobs.cancel(job_id, actor))


@router.post(
    "/{requirement_id}/architecture-mapping/jobs/{job_id}/retry",
    response_model=ArchitectureJobResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def retry_mapping_job(
    requirement_id: str, job_id: str, jobs: MappingJobsDep, actor: KnowledgeActorDep
) -> ArchitectureJobResponse:
    _requirement_job(requirement_id, job_id, jobs, actor)
    return ArchitectureJobResponse.from_domain(jobs.retry(job_id, actor))


def _requirement_job(
    requirement_id: str, job_id: str, jobs: ArchitectureMappingJobs, actor: Actor
) -> ArchitectureJob:
    """The job, read with the actor's own access; a job of another Requirement is not found."""
    job = jobs.get_for_actor(job_id, actor)
    if job.subject_id != requirement_id:
        raise ArchitectureJobNotFoundError("Architecture mapping job was not found.")
    return job


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
