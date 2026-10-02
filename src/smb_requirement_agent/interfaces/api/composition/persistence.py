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

from smb_requirement_agent.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.application.ports.activity import ActivityReadPort, ReportingReadPort
from smb_requirement_agent.application.ports.actor_directory import ActorDirectoryPort
from smb_requirement_agent.application.ports.ai_jobs import (
    AiJobQueuePort,
    AiJobRepositoryPort,
)
from smb_requirement_agent.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.application.ports.architecture_jobs import (
    ArchitectureJobRepositoryPort,
)
from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureReleaseStatePort,
)
from smb_requirement_agent.application.ports.architecture_knowledge_repository import (
    ArchitectureKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.architecture_mapping_stats import (
    ArchitectureMappingStatsPort,
)
from smb_requirement_agent.application.ports.architecture_rag import (
    ArchitectureEvidenceIndexPort,
    EmbeddingPort,
)
from smb_requirement_agent.application.ports.architecture_tokenizer import (
    ArchitectureTokenizerPort,
)
from smb_requirement_agent.application.ports.attachment_ingestions import (
    AttachmentIngestionRepositoryPort,
)
from smb_requirement_agent.application.ports.breakdown_repository import BreakdownRepositoryPort
from smb_requirement_agent.application.ports.breakdown_review_repository import (
    BreakdownReviewRepositoryPort,
)
from smb_requirement_agent.application.ports.catalogue_candidates import (
    CatalogueCandidateRepositoryPort,
)
from smb_requirement_agent.application.ports.document_library import DocumentLibraryPort
from smb_requirement_agent.application.ports.document_repository import DocumentRepositoryPort
from smb_requirement_agent.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.application.ports.feature_repository import FeatureRepositoryPort
from smb_requirement_agent.application.ports.knowledge_events import KnowledgeEventOutboxPort
from smb_requirement_agent.application.ports.knowledge_index_generations import (
    KnowledgeIndexGenerationsPort,
)
from smb_requirement_agent.application.ports.notifications import NotificationRepositoryPort
from smb_requirement_agent.application.ports.organisation_repository import (
    OrganisationRepositoryPort,
)
from smb_requirement_agent.application.ports.reference_index import ReferenceIndexPort
from smb_requirement_agent.application.ports.reference_publications import (
    ReferencePublicationStatePort,
)
from smb_requirement_agent.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_draft_repository import (
    RequirementDraftRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_evidence_analyzer import (
    EvidenceFragmentCachePort,
)
from smb_requirement_agent.application.ports.requirement_indexing import (
    RequirementIndexProgressPort,
)
from smb_requirement_agent.application.ports.requirement_knowledge import (
    RequirementKnowledgeIndexPort,
    RequirementKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_repository import RequirementRepositoryPort
from smb_requirement_agent.application.ports.requirement_worklist import (
    CurrentWorklistProjectionPort,
    RequirementWorklistSnapshotPort,
)
from smb_requirement_agent.application.ports.sample_requirements import SampleRequirementsPort
from smb_requirement_agent.application.ports.saved_views import SavedViewRepositoryPort
from smb_requirement_agent.application.ports.source_dependencies import SourceDependencyPort
from smb_requirement_agent.application.ports.story_quality_repository import (
    StoryQualityRepositoryPort,
)
from smb_requirement_agent.application.ports.story_repository import (
    StoryChangeProposalRepositoryPort,
    StoryRepositoryPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.dependency_projection import DependencyProjection
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    GetKnowledgeReview,
)
from smb_requirement_agent.application.use_cases.requirement_worklist import (
    ListRequirementWorklist,
    RequirementWorklistReader,
)
from smb_requirement_agent.infrastructure.architecture.evidence_index import InMemoryEvidenceIndex
from smb_requirement_agent.infrastructure.architecture.knowledge_yaml import (
    seed_knowledge,
)
from smb_requirement_agent.infrastructure.architecture.postgres_evidence_index import (
    PostgresEvidenceIndex,
)
from smb_requirement_agent.infrastructure.config.options import (
    ConfigurationError,
    PersistenceProvider,
)
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence import (
    knowledge_index_generations,
    postgres_architecture_knowledge,
    postgres_catalogue_candidates,
    postgres_evidence_fragment_cache,
    postgres_knowledge_generations,
    postgres_organisation,
    postgres_requirement_knowledge,
)
from smb_requirement_agent.infrastructure.persistence.activity_projection import (
    InMemoryActivityReadAdapter,
)
from smb_requirement_agent.infrastructure.persistence.architecture_mapping_stats import (
    PostgresArchitectureMappingStats,
    RepositoryArchitectureMappingStats,
)
from smb_requirement_agent.infrastructure.persistence.architecture_release_state import (
    InMemoryArchitectureReleaseState,
    PostgresArchitectureReleaseState,
)
from smb_requirement_agent.infrastructure.persistence.attachment_ingestions import (
    InMemoryAttachmentIngestions,
    PostgresAttachmentIngestions,
)
from smb_requirement_agent.infrastructure.persistence.document_library import (
    InMemoryDocumentLibrary,
    PostgresDocumentLibrary,
    PublishingDocumentLibrary,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_ai_jobs import (
    InMemoryAiJobStore,
    InMemoryNotificationRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_analysis_audit_repository import (
    InMemoryAnalysisAuditRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_analysis_repository import (
    InMemoryRequirementAnalysisRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_architecture_jobs import (
    InMemoryArchitectureJobs,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_architecture_knowledge import (
    InMemoryArchitectureKnowledgeRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_breakdown_review_repository import (
    InMemoryBreakdownReviewRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_catalogue_candidates import (
    InMemoryCatalogueCandidates,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_document_repository import (
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_epic_repository import (
    InMemoryEpicRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_evidence_fragment_cache import (
    InMemoryEvidenceFragmentCache,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_feature_repository import (
    InMemoryFeatureRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_identity import (
    InMemoryAccessRepository,
    InMemoryActorDirectory,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_organisation import (
    InMemoryOrganisationRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_requirement_draft_repository import (  # noqa: E501
    InMemoryRequirementDraftRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_requirement_repository import (
    InMemoryRequirementRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_revision_repository import (
    InMemoryRevisionRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_sample_requirements import (
    InMemorySampleRequirements,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_saved_views import (
    InMemorySavedViewRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_story_repository import (
    InMemoryStoryChangeProposalRepository,
    InMemoryStoryRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_transaction import (
    InMemoryTransactionManager,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_worklist import (
    InMemoryCurrentWorklistProjection,
    InMemoryRequirementWorklistSnapshotAdapter,
)
from smb_requirement_agent.infrastructure.persistence.knowledge_events import (
    InMemoryKnowledgeEvents,
    PostgresKnowledgeEvents,
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
from smb_requirement_agent.infrastructure.persistence.postgres_ai_jobs import (
    PostgresAiJobStore,
    PostgresNotificationRepository,
)
from smb_requirement_agent.infrastructure.persistence.postgres_architecture_jobs import (
    PostgresArchitectureJobs,
)
from smb_requirement_agent.infrastructure.persistence.postgres_document_repository import (
    PostgresDocumentRepository,
    PostgresDocumentStorage,
)
from smb_requirement_agent.infrastructure.persistence.postgres_repositories import (
    PostgresAccessRepository,
    PostgresActorDirectory,
    PostgresAnalysisAuditRepository,
    PostgresAnalysisRepository,
    PostgresBreakdownReviewRepository,
    PostgresEpicRepository,
    PostgresFeatureRepository,
    PostgresRequirementDraftRepository,
    PostgresRequirementRepository,
    PostgresStoryChangeProposalRepository,
    PostgresStoryRepository,
)
from smb_requirement_agent.infrastructure.persistence.postgres_revisions import (
    PostgresRevisionRepository,
    PostgresRevisionWriter,
)
from smb_requirement_agent.infrastructure.persistence.postgres_sample_requirements import (
    PostgresSampleRequirements,
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
from smb_requirement_agent.infrastructure.persistence.reference_index import (
    InMemoryReferenceIndex,
    PostgresReferenceIndex,
)
from smb_requirement_agent.infrastructure.persistence.reference_publications import (
    InMemoryReferencePublications,
    PostgresReferencePublications,
)
from smb_requirement_agent.infrastructure.persistence.relaying_architecture_knowledge import (
    RelayingArchitectureKnowledgeRepository,
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
from smb_requirement_agent.infrastructure.persistence.story_quality_repository import (
    InMemoryStoryQualityRepository,
    PostgresStoryQualityRepository,
)
from smb_requirement_agent.interfaces.api.composition.projections import (
    refresh_postgres_projections,
)


@dataclass(frozen=True)
class RequirementWorklistWiring:
    """How this backend reads the worklist and keeps its projection current."""

    reader: RequirementWorklistReader
    projection: CurrentWorklistProjectionPort


class KnowledgeRelay:
    """Drains the knowledge outbox into requirement work's local copies after a write.

    The projector is built after persistence, so it is bound later; until then
    a call does nothing and the polling worker catches up (ADR-0099).
    """

    def __init__(self) -> None:
        self._target: Callable[[], None] | None = None

    def bind(self, target: Callable[[], None]) -> None:
        self._target = target

    def __call__(self) -> None:
        if self._target is not None:
            self._target()


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
    architecture_repository: ArchitectureKnowledgeRepositoryPort
    organisation_repository: OrganisationRepositoryPort
    sample_requirements: SampleRequirementsPort
    architecture_mapping_stats: ArchitectureMappingStatsPort
    catalogue_candidates: CatalogueCandidateRepositoryPort
    architecture_evidence_index: ArchitectureEvidenceIndexPort
    architecture_job_repository: ArchitectureJobRepositoryPort
    mapping_job_repository: ArchitectureJobRepositoryPort
    library_repository: DocumentLibraryPort
    knowledge_events: KnowledgeEventOutboxPort
    reference_publications: ReferencePublicationStatePort
    architecture_releases: ArchitectureReleaseStatePort
    knowledge_relay: KnowledgeRelay
    attachment_ingestions: AttachmentIngestionRepositoryPort
    reference_index: ReferenceIndexPort
    revision_repository: BreakdownRepositoryPort
    transaction_manager: TransactionManagerPort
    dependency_index: SourceDependencyPort
    index_generations: KnowledgeIndexGenerationsPort | None
    requirement_index_progress: RequirementIndexProgressPort
    readiness_check: Callable[[], bool]
    worklist: Callable[[GetKnowledgeReview], RequirementWorklistWiring]


def build_persistence(
    settings: Settings,
    resources: ExitStack,
    resolved_clock: ClockPort,
    architecture_embeddings: EmbeddingPort,
    architecture_tokenizer: ArchitectureTokenizerPort,
) -> PersistenceAdapters:
    if settings.persistence_provider is PersistenceProvider.POSTGRES:
        return _postgres(
            settings, resources, resolved_clock, architecture_embeddings, architecture_tokenizer
        )
    return _memory(
        settings, resources, resolved_clock, architecture_embeddings, architecture_tokenizer
    )


def _postgres(
    settings: Settings,
    resources: ExitStack,
    resolved_clock: ClockPort,
    architecture_embeddings: EmbeddingPort,
    architecture_tokenizer: ArchitectureTokenizerPort,
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
    knowledge_relay = KnowledgeRelay()
    architecture_repository = RelayingArchitectureKnowledgeRepository(
        postgres_architecture_knowledge.PostgresArchitectureKnowledgeRepository(
            connector, seed_knowledge()
        ),
        knowledge_relay,
    )
    organisation_repository = postgres_organisation.PostgresOrganisationRepository(
        connector, resolved_clock
    )
    sample_requirements = PostgresSampleRequirements(connector)
    architecture_mapping_stats = PostgresArchitectureMappingStats(connector)
    catalogue_candidates = postgres_catalogue_candidates.PostgresCatalogueCandidates(connector)
    architecture_evidence_index = PostgresEvidenceIndex(
        connector, architecture_embeddings, architecture_tokenizer
    )
    architecture_job_repository = PostgresArchitectureJobs(connector)
    mapping_job_repository = PostgresArchitectureJobs(connector, table="requirement_mapping_jobs")
    knowledge_events: KnowledgeEventOutboxPort = PostgresKnowledgeEvents(postgres)
    reference_publications: ReferencePublicationStatePort = PostgresReferencePublications(postgres)
    architecture_releases: ArchitectureReleaseStatePort = PostgresArchitectureReleaseState(postgres)
    library_repository: DocumentLibraryPort = PublishingDocumentLibrary(
        PostgresDocumentLibrary(postgres), knowledge_events, reference_publications.apply
    )
    attachment_ingestions: AttachmentIngestionRepositoryPort = PostgresAttachmentIngestions(
        postgres
    )
    reference_index: ReferenceIndexPort = PostgresReferenceIndex(postgres)
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
        architecture_repository=architecture_repository,
        organisation_repository=organisation_repository,
        sample_requirements=sample_requirements,
        architecture_mapping_stats=architecture_mapping_stats,
        catalogue_candidates=catalogue_candidates,
        architecture_evidence_index=architecture_evidence_index,
        architecture_job_repository=architecture_job_repository,
        mapping_job_repository=mapping_job_repository,
        library_repository=library_repository,
        knowledge_events=knowledge_events,
        reference_publications=reference_publications,
        architecture_releases=architecture_releases,
        knowledge_relay=knowledge_relay,
        attachment_ingestions=attachment_ingestions,
        reference_index=reference_index,
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
    architecture_embeddings: EmbeddingPort,
    architecture_tokenizer: ArchitectureTokenizerPort,
) -> PersistenceAdapters:

    memory_lock = RLock()
    memory_knowledge = InMemoryRequirementKnowledgeStore(memory_lock)
    base_requirements = InMemoryRequirementRepository()
    requirement_draft_repository = InMemoryRequirementDraftRepository()
    document_repository = InMemoryDocumentRepository()
    document_storage = InMemoryDocumentStorage(lock=memory_lock)
    memory_events = InMemoryKnowledgeEvents(memory_lock)
    memory_releases = InMemoryArchitectureReleaseState(memory_lock)
    knowledge_relay = KnowledgeRelay()
    architecture_repository = RelayingArchitectureKnowledgeRepository(
        InMemoryArchitectureKnowledgeRepository(seed_knowledge(), memory_events), knowledge_relay
    )
    organisation_repository = InMemoryOrganisationRepository(resolved_clock)
    sample_requirements = InMemorySampleRequirements()
    catalogue_candidates = InMemoryCatalogueCandidates()
    architecture_evidence_index = InMemoryEvidenceIndex(
        architecture_embeddings, architecture_tokenizer
    )
    architecture_job_repository = InMemoryArchitectureJobs()
    mapping_job_repository = InMemoryArchitectureJobs()
    memory_library = InMemoryDocumentLibrary(memory_lock)
    memory_attachments = InMemoryAttachmentIngestions(memory_lock)
    attachment_ingestions = memory_attachments
    memory_publications = InMemoryReferencePublications(memory_lock)
    knowledge_events = memory_events
    reference_publications = memory_publications
    architecture_releases = memory_releases
    library_repository = PublishingDocumentLibrary(
        memory_library, memory_events, memory_publications.apply
    )
    memory_reference_index = InMemoryReferenceIndex(memory_lock, memory_library)
    reference_index = memory_reference_index
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
        memory_library,
        memory_events,
        memory_publications,
        memory_releases,
        memory_attachments,
        memory_reference_index,
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
        architecture_repository=architecture_repository,
        organisation_repository=organisation_repository,
        sample_requirements=sample_requirements,
        architecture_mapping_stats=architecture_mapping_stats,
        catalogue_candidates=catalogue_candidates,
        architecture_evidence_index=architecture_evidence_index,
        architecture_job_repository=architecture_job_repository,
        mapping_job_repository=mapping_job_repository,
        library_repository=library_repository,
        knowledge_events=knowledge_events,
        reference_publications=reference_publications,
        architecture_releases=architecture_releases,
        knowledge_relay=knowledge_relay,
        attachment_ingestions=attachment_ingestions,
        reference_index=reference_index,
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
