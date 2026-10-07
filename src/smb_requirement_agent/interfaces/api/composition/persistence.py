"""Persistence selection: every repository and port for one storage backend.

Memory and PostgreSQL provide the same set. A few composition decisions depend
on the backend beyond plain repositories — how the worklist is read and kept
current, where index progress lives, and how readiness is probed — so those
travel with the set instead of re-testing the provider elsewhere.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from threading import RLock

import httpx as httpx
from smb_kernel.documents.ports import DocumentStoragePort
from smb_kernel.persistence.connector import (
    POOL_MAX_IDLE_SECONDS,
    PooledPostgresConnector,
)
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.analysis.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.analysis.application.ports.requirement_evidence_analyzer import (
    EvidenceFragmentCachePort,
)
from smb_requirement_agent.analysis.infrastructure import postgres_evidence_fragment_cache
from smb_requirement_agent.analysis.infrastructure.in_memory_analysis_audit_repository import (
    InMemoryAnalysisAuditRepository,
)
from smb_requirement_agent.analysis.infrastructure.in_memory_analysis_repository import (
    InMemoryRequirementAnalysisRepository,
)
from smb_requirement_agent.analysis.infrastructure.in_memory_evidence_fragment_cache import (
    InMemoryEvidenceFragmentCache,
)
from smb_requirement_agent.analysis.infrastructure.postgres_analysis import (
    PostgresAnalysisAuditRepository,
    PostgresAnalysisRepository,
)
from smb_requirement_agent.application.ports.activity import ActivityReadPort, ReportingReadPort
from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureReleaseStatePort,
)
from smb_requirement_agent.application.ports.breakdown_repository import BreakdownRepositoryPort
from smb_requirement_agent.application.ports.breakdown_review_repository import (
    BreakdownReviewRepositoryPort,
)
from smb_requirement_agent.application.ports.corpus_membership import (
    CorpusActionsPort,
    CorpusMembershipPort,
    SourceChangesPort,
)
from smb_requirement_agent.application.ports.corpus_summary import CorpusCountsPort
from smb_requirement_agent.application.ports.historic_corpus import HistoricCorpusPort
from smb_requirement_agent.application.ports.knowledge_handoff import ApprovedBacklogOutboxPort
from smb_requirement_agent.application.ports.knowledge_index_generations import (
    KnowledgeIndexGenerationsPort,
)
from smb_requirement_agent.application.ports.knowledge_portfolio import (
    FindingNudgesPort,
    KnowledgePortfolioPort,
)
from smb_requirement_agent.application.ports.prior_art import PriorArtStorePort
from smb_requirement_agent.application.ports.reference_publications import (
    ReferencePublicationStatePort,
)
from smb_requirement_agent.application.ports.requirement_indexing import (
    RequirementIndexProgressPort,
)
from smb_requirement_agent.application.ports.requirement_knowledge import (
    RequirementKnowledgeIndexPort,
    RequirementKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_worklist import (
    CurrentWorklistProjectionPort,
    RequirementWorklistSnapshotPort,
)
from smb_requirement_agent.application.ports.saved_views import SavedViewRepositoryPort
from smb_requirement_agent.application.ports.source_dependencies import SourceDependencyPort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.dependency_projection import DependencyProjection
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    GetKnowledgeReview,
)
from smb_requirement_agent.application.use_cases.requirement_worklist import (
    ListRequirementWorklist,
    RequirementWorklistReader,
)
from smb_requirement_agent.breakdown.application.ports.architecture_jobs import (
    ArchitectureJobRepositoryPort,
)
from smb_requirement_agent.breakdown.application.ports.architecture_mapping_stats import (
    ArchitectureMappingStatsPort,
)
from smb_requirement_agent.breakdown.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.breakdown.application.ports.feature_repository import (
    FeatureRepositoryPort,
)
from smb_requirement_agent.breakdown.application.ports.story_quality_repository import (
    StoryQualityRepositoryPort,
)
from smb_requirement_agent.breakdown.application.ports.story_repository import (
    StoryChangeProposalRepositoryPort,
    StoryRepositoryPort,
)
from smb_requirement_agent.breakdown.infrastructure.architecture_mapping_stats import (
    PostgresArchitectureMappingStats,
    RepositoryArchitectureMappingStats,
)
from smb_requirement_agent.breakdown.infrastructure.in_memory_architecture_jobs import (
    InMemoryArchitectureJobs,
)
from smb_requirement_agent.breakdown.infrastructure.in_memory_epic_repository import (
    InMemoryEpicRepository,
)
from smb_requirement_agent.breakdown.infrastructure.in_memory_feature_repository import (
    InMemoryFeatureRepository,
)
from smb_requirement_agent.breakdown.infrastructure.in_memory_story_repository import (
    InMemoryStoryChangeProposalRepository,
    InMemoryStoryRepository,
)
from smb_requirement_agent.breakdown.infrastructure.postgres_architecture_jobs import (
    PostgresArchitectureJobs,
)
from smb_requirement_agent.breakdown.infrastructure.postgres_backlog import (
    PostgresEpicRepository,
    PostgresFeatureRepository,
    PostgresStoryChangeProposalRepository,
    PostgresStoryRepository,
)
from smb_requirement_agent.breakdown.infrastructure.story_quality_repository import (
    InMemoryStoryQualityRepository,
    PostgresStoryQualityRepository,
)
from smb_requirement_agent.identity.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.identity.application.ports.actor_directory import ActorDirectoryPort
from smb_requirement_agent.identity.infrastructure.in_memory_identity import (
    InMemoryAccessRepository,
    InMemoryActorDirectory,
)
from smb_requirement_agent.identity.infrastructure.postgres_identity import (
    PostgresAccessRepository,
    PostgresActorDirectory,
)
from smb_requirement_agent.infrastructure.config.options import (
    ConfigurationError,
    PersistenceProvider,
)
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence import (
    knowledge_index_generations,
    postgres_knowledge_generations,
    postgres_requirement_knowledge,
)
from smb_requirement_agent.infrastructure.persistence.activity_projection import (
    InMemoryActivityReadAdapter,
)
from smb_requirement_agent.infrastructure.persistence.architecture_release_state import (
    InMemoryArchitectureReleaseState,
    PostgresArchitectureReleaseState,
)
from smb_requirement_agent.infrastructure.persistence.backlog_handoffs import (
    InMemoryBacklogHandoffs,
    PostgresBacklogHandoffs,
)
from smb_requirement_agent.infrastructure.persistence.corpus_counts import (
    PostgresCorpusCounts,
    RepositoryCorpusCounts,
)
from smb_requirement_agent.infrastructure.persistence.corpus_membership import (
    InMemoryCorpusActions,
    InMemoryCorpusMembership,
    InMemorySourceChanges,
    PostgresCorpusActions,
    PostgresCorpusMembership,
    PostgresSourceChanges,
)
from smb_requirement_agent.infrastructure.persistence.historic_corpus import (
    InMemoryHistoricCorpus,
    PostgresHistoricCorpus,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_breakdown_review_repository import (
    InMemoryBreakdownReviewRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_revision_repository import (
    InMemoryRevisionRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_saved_views import (
    InMemorySavedViewRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_transaction import (
    InMemoryTransactionManager,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_worklist import (
    InMemoryCurrentWorklistProjection,
    InMemoryRequirementWorklistSnapshotAdapter,
)
from smb_requirement_agent.infrastructure.persistence.knowledge_portfolio import (
    InMemoryFindingNudges,
    PostgresFindingNudges,
    PostgresKnowledgePortfolio,
    RepositoryKnowledgePortfolio,
)
from smb_requirement_agent.infrastructure.persistence.postgres_activity import (
    PostgresProjectedActivity,
)
from smb_requirement_agent.infrastructure.persistence.postgres_activity_reader import (
    PostgresActivityReadAdapter,
)
from smb_requirement_agent.infrastructure.persistence.postgres_activity_sources import (
    PostgresActivitySources,
)
from smb_requirement_agent.infrastructure.persistence.postgres_repositories import (
    PostgresBreakdownReviewRepository,
)
from smb_requirement_agent.infrastructure.persistence.postgres_revisions import (
    PostgresRevisionRepository,
    PostgresRevisionWriter,
)
from smb_requirement_agent.infrastructure.persistence.postgres_saved_views import (
    PostgresSavedViewRepository,
)
from smb_requirement_agent.infrastructure.persistence.postgres_snapshots import (
    PostgresSnapshotReader,
)
from smb_requirement_agent.infrastructure.persistence.postgres_store import PostgresStore
from smb_requirement_agent.infrastructure.persistence.postgres_worklist import (
    PostgresRequirementWorklistReader,
    PostgresWorklistProjectionMaintainer,
)
from smb_requirement_agent.infrastructure.persistence.prior_art import (
    InMemoryPriorArt,
    PostgresPriorArt,
)
from smb_requirement_agent.infrastructure.persistence.reference_publications import (
    InMemoryReferencePublications,
    PostgresReferencePublications,
)
from smb_requirement_agent.infrastructure.persistence.requirement_indexing import (
    MemoryRequirementIndexProgress,
    PostgresRequirementIndexProgress,
)
from smb_requirement_agent.infrastructure.persistence.requirement_knowledge_repository import (  # noqa: E501
    InMemoryRequirementKnowledgeStore,
)
from smb_requirement_agent.infrastructure.persistence.revision_tracking import (
    TrackingAccessRepository,
    TrackingAnalysisRepository,
    TrackingBreakdownReviewRepository,
    TrackingEpicRepository,
    TrackingFeatureRepository,
    TrackingRequirementRepository,
    TrackingStoryRepository,
)
from smb_requirement_agent.infrastructure.persistence.source_dependencies import (
    InMemorySourceDependencies,
    PostgresSourceDependencies,
)
from smb_requirement_agent.interfaces.api.composition.projections import (
    refresh_postgres_projections,
)
from smb_requirement_agent.jobs.application.ports.ai_jobs import (
    AiJobQueuePort,
    AiJobRepositoryPort,
)
from smb_requirement_agent.jobs.application.ports.notifications import NotificationRepositoryPort
from smb_requirement_agent.jobs.infrastructure.in_memory_ai_jobs import (
    InMemoryAiJobStore,
    InMemoryNotificationRepository,
)
from smb_requirement_agent.jobs.infrastructure.postgres_ai_jobs import (
    PostgresAiJobStore,
    PostgresNotificationRepository,
)
from smb_requirement_agent.requirements.application.ports.attachment_ingestions import (
    AttachmentIngestionRepositoryPort,
)
from smb_requirement_agent.requirements.application.ports.document_repository import (
    DocumentRepositoryPort,
)
from smb_requirement_agent.requirements.application.ports.requirement_draft_repository import (
    RequirementDraftRepositoryPort,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.infrastructure.attachment_ingestions import (
    InMemoryAttachmentIngestions,
    PostgresAttachmentIngestions,
)
from smb_requirement_agent.requirements.infrastructure.in_memory_document_repository import (
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
)
from smb_requirement_agent.requirements.infrastructure.in_memory_requirement_draft_repository import (  # noqa: E501
    InMemoryRequirementDraftRepository,
)
from smb_requirement_agent.requirements.infrastructure.in_memory_requirement_repository import (
    InMemoryRequirementRepository,
)
from smb_requirement_agent.requirements.infrastructure.postgres_document_repository import (
    PostgresDocumentRepository,
    PostgresDocumentStorage,
)
from smb_requirement_agent.requirements.infrastructure.postgres_requirements import (
    PostgresRequirementDraftRepository,
    PostgresRequirementRepository,
)


@dataclass(frozen=True)
class RequirementWorklistWiring:
    """How this backend reads the worklist and keeps its projection current."""

    reader: RequirementWorklistReader
    projection: CurrentWorklistProjectionPort


@dataclass(frozen=True)
class PersistenceAdapters:
    requirement_repository: RequirementRepositoryPort
    requirement_draft_repository: RequirementDraftRepositoryPort
    document_repository: DocumentRepositoryPort
    document_storage: DocumentStoragePort
    analysis_repository: RequirementAnalysisRepositoryPort
    analysis_audit_repository: AnalysisAuditRepositoryPort
    epic_repository: EpicRepositoryPort
    feature_repository: FeatureRepositoryPort
    story_repository: StoryRepositoryPort
    story_proposal_repository: StoryChangeProposalRepositoryPort
    breakdown_review_repository: BreakdownReviewRepositoryPort
    worklist_snapshots: RequirementWorklistSnapshotPort
    access_repository: AccessRepositoryPort
    actor_directory: ActorDirectoryPort
    ai_job_repository: AiJobRepositoryPort
    ai_job_queue: AiJobQueuePort
    notification_repository: NotificationRepositoryPort
    story_quality_repository: StoryQualityRepositoryPort
    saved_view_repository: SavedViewRepositoryPort
    activity_reader: ActivityReadPort
    reporting_reader: ReportingReadPort
    knowledge_index: RequirementKnowledgeIndexPort
    knowledge_repository: RequirementKnowledgeRepositoryPort
    evidence_fragment_cache: EvidenceFragmentCachePort
    architecture_mapping_stats: ArchitectureMappingStatsPort
    corpus_counts: CorpusCountsPort
    knowledge_portfolio: KnowledgePortfolioPort
    finding_nudges: FindingNudgesPort
    corpus_membership: CorpusMembershipPort
    corpus_actions: CorpusActionsPort
    source_changes: SourceChangesPort
    mapping_job_repository: ArchitectureJobRepositoryPort
    reference_publications: ReferencePublicationStatePort
    architecture_releases: ArchitectureReleaseStatePort
    # Historic requirements and their corpus (Knowledge Center E2, ADR-0102).
    historic_corpus: HistoricCorpusPort
    prior_art: PriorArtStorePort
    attachment_ingestions: AttachmentIngestionRepositoryPort
    # Approved backlogs on their way to the knowledge service (ADR-0101 Amendment 2).
    backlog_handoffs: ApprovedBacklogOutboxPort
    revision_repository: BreakdownRepositoryPort
    transaction_manager: TransactionManagerPort
    dependency_index: SourceDependencyPort
    index_generations: KnowledgeIndexGenerationsPort | None
    requirement_index_progress: RequirementIndexProgressPort
    readiness_check: Callable[[], bool]
    worklist: Callable[[GetKnowledgeReview], RequirementWorklistWiring]


def build_persistence(
    settings: Settings, resources: ExitStack, resolved_clock: ClockPort
) -> PersistenceAdapters:
    if settings.persistence_provider is PersistenceProvider.POSTGRES:
        return _postgres(settings, resources, resolved_clock)
    return _memory(settings, resources, resolved_clock)


def _postgres(
    settings: Settings,
    resources: ExitStack,
    resolved_clock: ClockPort,
) -> PersistenceAdapters:
    # Imported here, not at module load, so memory/fake runs never need the
    # PostgreSQL driver (psycopg) installed. Only this branch requires it.

    if settings.database_url is None:  # guarded by Settings, keeps mypy explicit
        raise ConfigurationError("PERSISTENCE_PROVIDER=postgres requires DATABASE_URL.")
    connector = PooledPostgresConnector(
        settings.database_url,
        min_size=settings.database_pool_min_size,
        max_size=settings.database_pool_max_size,
        acquire_timeout_seconds=settings.database_pool_timeout_seconds,
        max_idle_seconds=POOL_MAX_IDLE_SECONDS,
        name="requirement-portal",
    )
    connector.open()
    # Registered first so it closes last, after every adapter and worker.
    resources.callback(connector.close)
    postgres = PostgresStore(
        connector, PostgresRevisionWriter().capture, refresh_postgres_projections
    )
    requirement_repository = PostgresRequirementRepository(postgres)
    requirement_draft_repository = PostgresRequirementDraftRepository(postgres)
    document_repository = PostgresDocumentRepository(postgres)
    document_storage = PostgresDocumentStorage(postgres)
    architecture_mapping_stats = PostgresArchitectureMappingStats(connector)
    corpus_counts = PostgresCorpusCounts(connector)
    knowledge_portfolio: KnowledgePortfolioPort = PostgresKnowledgePortfolio(connector)
    finding_nudges: FindingNudgesPort = PostgresFindingNudges(postgres)
    corpus_membership: CorpusMembershipPort = PostgresCorpusMembership(postgres)
    corpus_actions: CorpusActionsPort = PostgresCorpusActions(postgres)
    source_changes: SourceChangesPort = PostgresSourceChanges(postgres)
    mapping_job_repository = PostgresArchitectureJobs(connector)
    reference_publications: ReferencePublicationStatePort = PostgresReferencePublications(postgres)
    historic_corpus: HistoricCorpusPort = PostgresHistoricCorpus(postgres)
    prior_art: PriorArtStorePort = PostgresPriorArt(postgres)
    architecture_releases: ArchitectureReleaseStatePort = PostgresArchitectureReleaseState(postgres)
    attachment_ingestions: AttachmentIngestionRepositoryPort = PostgresAttachmentIngestions(
        postgres
    )
    backlog_handoffs: ApprovedBacklogOutboxPort = PostgresBacklogHandoffs(postgres)
    analysis_repository = PostgresAnalysisRepository(postgres)
    analysis_audit_repository = PostgresAnalysisAuditRepository(postgres)
    epic_repository = PostgresEpicRepository(postgres)
    feature_repository = PostgresFeatureRepository(postgres)
    story_repository = PostgresStoryRepository(postgres)
    story_proposal_repository = PostgresStoryChangeProposalRepository(postgres)
    breakdown_review_repository = PostgresBreakdownReviewRepository(postgres)
    postgres_revisions = PostgresRevisionRepository(postgres)
    revision_repository: BreakdownRepositoryPort = postgres_revisions
    transaction_manager: TransactionManagerPort = postgres
    dependency_index: SourceDependencyPort = PostgresSourceDependencies(postgres)
    worklist_snapshots = PostgresSnapshotReader(postgres)
    access_repository = PostgresAccessRepository(postgres)
    actor_directory = PostgresActorDirectory(postgres)
    postgres_ai_jobs = PostgresAiJobStore(postgres)
    ai_job_repository = postgres_ai_jobs
    ai_job_queue = postgres_ai_jobs
    notification_repository = PostgresNotificationRepository(postgres)
    story_quality_repository = PostgresStoryQualityRepository(postgres)
    saved_view_repository = PostgresSavedViewRepository(postgres)
    postgres_knowledge = postgres_requirement_knowledge.PostgresRequirementKnowledgeStore(postgres)
    knowledge_index: RequirementKnowledgeIndexPort = postgres_knowledge
    index_generations: KnowledgeIndexGenerationsPort | None = None
    if settings.llm_profiles:
        index_generations = postgres_knowledge_generations.PostgresKnowledgeIndexGenerations(
            postgres
        )
        knowledge_index = index_generations.active_index(
            settings.llm_profiles.selected_embedding.identity
        )
    knowledge_repository = postgres_knowledge
    evidence_fragment_cache = postgres_evidence_fragment_cache.PostgresEvidenceFragmentCache(
        postgres
    )

    activity_source = PostgresActivityReadAdapter(
        PostgresActivitySources(postgres, worklist_snapshots, postgres_revisions),
        postgres_ai_jobs,
        knowledge_repository,
        analysis_audit_repository,
    )
    projected_activity = PostgresProjectedActivity(postgres, activity_source)
    activity_reader = projected_activity

    def postgres_worklist(get_knowledge_review: GetKnowledgeReview) -> RequirementWorklistWiring:

        return RequirementWorklistWiring(
            reader=PostgresRequirementWorklistReader(postgres, worklist_snapshots),
            projection=PostgresWorklistProjectionMaintainer(
                postgres,
                worklist_snapshots,
                get_knowledge_review,
                activity_reader,
                projected_activity,
            ),
        )

    return PersistenceAdapters(
        requirement_repository=requirement_repository,
        requirement_draft_repository=requirement_draft_repository,
        document_repository=document_repository,
        document_storage=document_storage,
        analysis_repository=analysis_repository,
        analysis_audit_repository=analysis_audit_repository,
        epic_repository=epic_repository,
        feature_repository=feature_repository,
        story_repository=story_repository,
        story_proposal_repository=story_proposal_repository,
        breakdown_review_repository=breakdown_review_repository,
        worklist_snapshots=worklist_snapshots,
        access_repository=access_repository,
        actor_directory=actor_directory,
        ai_job_repository=ai_job_repository,
        ai_job_queue=ai_job_queue,
        notification_repository=notification_repository,
        story_quality_repository=story_quality_repository,
        saved_view_repository=saved_view_repository,
        activity_reader=activity_reader,
        reporting_reader=activity_reader,
        knowledge_index=knowledge_index,
        knowledge_repository=knowledge_repository,
        evidence_fragment_cache=evidence_fragment_cache,
        architecture_mapping_stats=architecture_mapping_stats,
        corpus_counts=corpus_counts,
        knowledge_portfolio=knowledge_portfolio,
        finding_nudges=finding_nudges,
        corpus_membership=corpus_membership,
        corpus_actions=corpus_actions,
        source_changes=source_changes,
        mapping_job_repository=mapping_job_repository,
        reference_publications=reference_publications,
        architecture_releases=architecture_releases,
        historic_corpus=historic_corpus,
        prior_art=prior_art,
        attachment_ingestions=attachment_ingestions,
        backlog_handoffs=backlog_handoffs,
        revision_repository=revision_repository,
        transaction_manager=transaction_manager,
        dependency_index=dependency_index,
        index_generations=index_generations,
        requirement_index_progress=PostgresRequirementIndexProgress(postgres),
        readiness_check=postgres.readiness,
        worklist=postgres_worklist,
    )


def _memory(
    settings: Settings,
    resources: ExitStack,
    resolved_clock: ClockPort,
) -> PersistenceAdapters:

    memory_lock = RLock()
    memory_knowledge = InMemoryRequirementKnowledgeStore(memory_lock)
    base_requirements = InMemoryRequirementRepository()
    requirement_draft_repository = InMemoryRequirementDraftRepository()
    document_repository = InMemoryDocumentRepository(memory_knowledge.mark_source_changed)
    document_storage = InMemoryDocumentStorage(lock=memory_lock)
    memory_releases = InMemoryArchitectureReleaseState(memory_lock)
    mapping_job_repository = InMemoryArchitectureJobs()
    memory_attachments = InMemoryAttachmentIngestions(memory_lock)
    attachment_ingestions = memory_attachments
    memory_handoffs = InMemoryBacklogHandoffs(memory_lock)
    memory_publications = InMemoryReferencePublications(memory_lock)
    reference_publications = memory_publications
    memory_historic = InMemoryHistoricCorpus(memory_lock)
    memory_prior_art = InMemoryPriorArt(memory_lock)
    architecture_releases = memory_releases
    base_analyses = InMemoryRequirementAnalysisRepository()
    analysis_audit_repository = InMemoryAnalysisAuditRepository(
        memory_knowledge.mark_source_changed
    )
    base_epics = InMemoryEpicRepository()
    base_features = InMemoryFeatureRepository()
    base_stories = InMemoryStoryRepository()
    base_reviews = InMemoryBreakdownReviewRepository()
    base_access = InMemoryAccessRepository()
    actor_directory = InMemoryActorDirectory(lock=memory_lock)
    story_proposal_repository = InMemoryStoryChangeProposalRepository()
    memory_ai_jobs = InMemoryAiJobStore(memory_lock)
    ai_job_repository = memory_ai_jobs
    ai_job_queue = memory_ai_jobs
    notification_repository = InMemoryNotificationRepository(memory_ai_jobs)

    story_quality_repository = InMemoryStoryQualityRepository()
    saved_view_repository = InMemorySavedViewRepository(lock=memory_lock)
    memory_transactions = InMemoryTransactionManager(
        memory_knowledge.mark_source_changed, memory_lock
    )
    revision_repository = InMemoryRevisionRepository(
        base_requirements,
        base_analyses,
        base_epics,
        base_features,
        base_stories,
        base_reviews,
        base_access,
        resolved_clock,
    )
    requirement_repository = TrackingRequirementRepository(
        base_requirements, revision_repository, memory_transactions
    )
    analysis_repository = TrackingAnalysisRepository(
        base_analyses, revision_repository, memory_transactions
    )
    epic_repository = TrackingEpicRepository(base_epics, revision_repository, memory_transactions)
    feature_repository = TrackingFeatureRepository(
        base_features,
        base_epics.requirement_id_for_epic,
        revision_repository,
        memory_transactions,
    )
    story_repository = TrackingStoryRepository(
        base_stories,
        base_features.epic_id_for_feature,
        base_epics.requirement_id_for_epic,
        revision_repository,
        memory_transactions,
    )
    memory_membership = InMemoryCorpusMembership(memory_lock, memory_knowledge.mark_source_changed)
    memory_transactions.enroll(memory_membership)
    corpus_membership = memory_membership
    corpus_counts = RepositoryCorpusCounts(
        requirement_repository, memory_knowledge.raised_findings, memory_membership
    )
    architecture_mapping_stats = RepositoryArchitectureMappingStats(
        requirement_repository, epic_repository, feature_repository, story_repository
    )
    breakdown_review_repository = TrackingBreakdownReviewRepository(
        base_reviews, revision_repository, memory_transactions
    )
    access_repository = TrackingAccessRepository(
        base_access, revision_repository, memory_transactions
    )
    transaction_manager = memory_transactions
    memory_nudges = InMemoryFindingNudges(memory_lock)
    memory_transactions.enroll(memory_nudges)
    finding_nudges = memory_nudges
    memory_actions = InMemoryCorpusActions(memory_lock)
    memory_transactions.enroll(memory_actions)
    corpus_actions = memory_actions
    source_changes = InMemorySourceChanges(
        lambda requirement_id: requirement_repository.get(requirement_id) is not None,
        memory_knowledge.mark_source_changed,
    )
    knowledge_portfolio = RepositoryKnowledgePortfolio(
        requirement_repository,
        access_repository,
        memory_knowledge,
        memory_nudges,
        memory_membership,
    )
    worklist_snapshots = InMemoryRequirementWorklistSnapshotAdapter(
        requirement_repository,
        analysis_repository,
        epic_repository,
        feature_repository,
        story_repository,
        revision_repository,
        access_repository,
        analysis_audit_repository,
        ai_job_repository,
        breakdown_review_repository,
    )
    memory_dependencies = InMemorySourceDependencies(access_repository)
    dependency_index = memory_dependencies
    memory_transactions.enroll(memory_dependencies)
    memory_transactions.project_on_commit(
        DependencyProjection(worklist_snapshots, dependency_index).refresh
    )

    current_worklist_projection: CurrentWorklistProjectionPort = InMemoryCurrentWorklistProjection()
    knowledge_index: RequirementKnowledgeIndexPort = memory_knowledge
    index_generations = None
    if settings.llm_profiles:
        memory_generations = knowledge_index_generations.InMemoryKnowledgeIndexGenerations(
            memory_knowledge, memory_lock
        )
        memory_transactions.enroll(memory_generations)
        index_generations = memory_generations
        knowledge_index = index_generations.active_index(
            settings.llm_profiles.selected_embedding.identity
        )
    knowledge_repository = memory_knowledge
    evidence_fragment_cache = InMemoryEvidenceFragmentCache()
    memory_transactions.enroll(
        memory_publications,
        memory_historic,
        memory_prior_art,
        memory_releases,
        memory_attachments,
        memory_handoffs,
        base_requirements,
        requirement_draft_repository,
        document_repository,
        document_storage,
        base_analyses,
        analysis_audit_repository,
        base_epics,
        base_features,
        base_stories,
        base_reviews,
        base_access,
        actor_directory,
        story_proposal_repository,
        memory_ai_jobs,
        story_quality_repository,
        saved_view_repository,
        revision_repository,
        memory_knowledge,
        evidence_fragment_cache,
    )
    activity_reader = InMemoryActivityReadAdapter(
        worklist_snapshots,
        revision_repository,
        analysis_audit_repository,
        ai_job_repository,
        knowledge_repository,
    )

    def memory_worklist(get_knowledge_review: GetKnowledgeReview) -> RequirementWorklistWiring:
        return RequirementWorklistWiring(
            reader=ListRequirementWorklist(
                worklist_snapshots, activity_reader, get_knowledge_review
            ),
            projection=current_worklist_projection,
        )

    return PersistenceAdapters(
        requirement_repository=requirement_repository,
        requirement_draft_repository=requirement_draft_repository,
        document_repository=document_repository,
        document_storage=document_storage,
        analysis_repository=analysis_repository,
        analysis_audit_repository=analysis_audit_repository,
        epic_repository=epic_repository,
        feature_repository=feature_repository,
        story_repository=story_repository,
        story_proposal_repository=story_proposal_repository,
        breakdown_review_repository=breakdown_review_repository,
        worklist_snapshots=worklist_snapshots,
        access_repository=access_repository,
        actor_directory=actor_directory,
        ai_job_repository=ai_job_repository,
        ai_job_queue=ai_job_queue,
        notification_repository=notification_repository,
        story_quality_repository=story_quality_repository,
        saved_view_repository=saved_view_repository,
        activity_reader=activity_reader,
        reporting_reader=activity_reader,
        knowledge_index=knowledge_index,
        knowledge_repository=knowledge_repository,
        evidence_fragment_cache=evidence_fragment_cache,
        architecture_mapping_stats=architecture_mapping_stats,
        corpus_counts=corpus_counts,
        knowledge_portfolio=knowledge_portfolio,
        finding_nudges=finding_nudges,
        corpus_membership=corpus_membership,
        corpus_actions=corpus_actions,
        source_changes=source_changes,
        mapping_job_repository=mapping_job_repository,
        reference_publications=reference_publications,
        architecture_releases=architecture_releases,
        historic_corpus=memory_historic,
        prior_art=memory_prior_art,
        attachment_ingestions=attachment_ingestions,
        backlog_handoffs=memory_handoffs,
        revision_repository=revision_repository,
        transaction_manager=transaction_manager,
        dependency_index=dependency_index,
        index_generations=index_generations,
        requirement_index_progress=MemoryRequirementIndexProgress(memory_lock),
        readiness_check=_always_ready,
        worklist=memory_worklist,
    )


def _always_ready() -> bool:
    return True
