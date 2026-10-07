"""Mapping a Requirement's backlog to the architecture catalogue, as queued requirement work.

The catalogue and its matching live in the knowledge service (ADR-0099); this
process maps its own backlog against the release its local copy names, through
`ArchitectureKnowledgePort`.
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ActiveArchitectureReleasePort,
)
from smb_requirement_agent.breakdown.application.use_cases.architecture_mapping import (
    MapBreakdownArchitecture,
)
from smb_requirement_agent.breakdown.application.use_cases.architecture_mapping_jobs import (
    ArchitectureMappingJobs,
)
from smb_requirement_agent.breakdown.application.use_cases.leased_jobs import (
    ArchitectureJobExecution,
)
from smb_requirement_agent.breakdown.infrastructure.architecture_job_worker import (
    ArchitectureJobWorker,
)
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters


@dataclass(frozen=True)
class ArchitectureJobWiring:
    mapping_jobs: ArchitectureMappingJobs
    # Present only when jobs are queued; inline jobs finish inside the request.
    mapping_worker: ArchitectureJobWorker | None


def build_architecture_jobs(
    settings: Settings,
    persistence: PersistenceAdapters,
    map_breakdown_architecture: MapBreakdownArchitecture,
    clock: ClockPort,
    current_release: ActiveArchitectureReleasePort,
) -> ArchitectureJobWiring:
    # Offline fake models complete jobs inside the starting request; real models
    # queue them for the background worker.
    execution = (
        ArchitectureJobExecution.INLINE
        if settings.llm_provider is LLMProvider.FAKE
        else ArchitectureJobExecution.QUEUED
    )
    # Matching runs in the knowledge service; a mapping is current for the release
    # it pinned and the service it asked, which these name.
    matcher = settings.knowledge_api_base_url or "in-process"
    mapping_jobs = ArchitectureMappingJobs(
        persistence.mapping_job_repository,
        current_release,
        map_breakdown_architecture,
        execution,
        f"knowledge-service:{matcher}",
        "knowledge-service:architecture-impact-v1",
        clock,
    )
    return ArchitectureJobWiring(
        mapping_jobs=mapping_jobs,
        mapping_worker=ArchitectureJobWorker(
            mapping_jobs,
            poll_interval_seconds=settings.ai_job_poll_interval_seconds,
            shutdown_grace_seconds=settings.ai_job_shutdown_grace_seconds,
            name="architecture-mapping-jobs",
        )
        if execution is ArchitectureJobExecution.QUEUED
        else None,
    )
