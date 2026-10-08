"""Durable AI jobs: starting them, executing them, and the workers that claim them."""

from __future__ import annotations

from dataclasses import dataclass

from smb_kernel.observability.metrics import Metrics
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.jobs.prior_art_gate import PriorArtGatedQueue
from smb_requirement_agent.infrastructure.jobs.requirement_index_worker import IndexReadyJobQueue
from smb_requirement_agent.interfaces.api.composition.analysis import (
    AnalysisWorkflowWiring,
)
from smb_requirement_agent.interfaces.api.composition.breakdown import BreakdownWiring
from smb_requirement_agent.interfaces.api.composition.knowledge import RequirementKnowledgeWiring
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters
from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobWorkerPort
from smb_requirement_agent.workflows.application.use_cases.ai_job_execution import ExecuteAiJob
from smb_requirement_agent.workflows.application.use_cases.ai_jobs import AiJobs, Notifications
from smb_requirement_agent.workflows.application.use_cases.identity_access import (
    RequirementAccessService,
)
from smb_requirement_agent.workflows.infrastructure.polling_worker import (
    AiJobWorkerGroup,
    PollingAiJobWorker,
)


@dataclass(frozen=True)
class AiJobWiring:
    ai_jobs: AiJobs
    notifications: Notifications
    execute_ai_job: ExecuteAiJob
    worker: AiJobWorkerPort


def build_ai_jobs(
    settings: Settings,
    persistence: PersistenceAdapters,
    analysis: AnalysisWorkflowWiring,
    breakdown: BreakdownWiring,
    knowledge: RequirementKnowledgeWiring,
    clock: ClockPort,
    access: RequirementAccessService,
    metrics: Metrics,
) -> AiJobWiring:
    execute = ExecuteAiJob(
        persistence.ai_job_repository,
        persistence.notification_repository,
        persistence.actor_directory,
        clock,
        persistence.transaction_manager,
        analysis.analyze_requirement,
        analysis.clarify_requirement_analysis,
        analysis.analysis_collaboration,
        breakdown.generate_epic,
        breakdown.generate_features,
        breakdown.generate_stories,
        breakdown.regenerate_story,
        breakdown.story_change_proposals,
        breakdown.evaluate_feature_stories,
        breakdown.generate_breakdown_review,
        breakdown.resolve_open_question,
        knowledge.screen,
        knowledge.suggest_answers,
        persistence.access_repository,
        access,
        analysis.generation_context_tokens,
        screen_prior_art=knowledge.screen_prior_art,
    )
    # Index-dependent operations wait behind the gate instead of failing.
    worker = AiJobWorkerGroup(
        tuple(
            PollingAiJobWorker(
                IndexReadyJobQueue(
                    PriorArtGatedQueue(
                        persistence.ai_job_queue,
                        persistence.prior_art,
                        clock,
                        enabled=settings.prior_art_enabled,
                        hourly=settings.prior_art_judge_calls_per_hour,
                    ),
                    knowledge.indexer,
                ),
                execute,
                clock,
                metrics,
                poll_interval_seconds=settings.ai_job_poll_interval_seconds,
                lease_seconds=settings.ai_job_lease_seconds,
                heartbeat_seconds=settings.ai_job_heartbeat_seconds,
                shutdown_grace_seconds=settings.ai_job_shutdown_grace_seconds,
            )
            for _ in range(settings.ai_job_worker_concurrency)
        )
    )
    return AiJobWiring(
        ai_jobs=AiJobs(
            persistence.ai_job_repository,
            persistence.requirement_repository,
            access,
            clock,
            analysis.generation_context_tokens,
            persistence.transaction_manager,
        ),
        notifications=Notifications(persistence.notification_repository, clock),
        execute_ai_job=execute,
        worker=worker,
    )
