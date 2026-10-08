"""Composition root.

The single place where concrete adapters are chosen and use cases are wired.
Nothing here is created at import time: a container is built explicitly from
`Settings`, so configuration errors surface at startup and tests can build an
isolated graph per test instead of sharing process-wide singletons.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import ExitStack
from dataclasses import dataclass, replace
from typing import Protocol

from smb_kernel.diagnostics import DebugTrace
from smb_kernel.documents.ports import DocumentStoragePort
from smb_kernel.identity.ports import IdentityProviderPort
from smb_kernel.observability.metrics import Metrics
from smb_kernel.time.clock import ClockPort
from smb_kernel.time.system import SystemClock

from smb_requirement_agent.analysis.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.analysis.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    RequirementAnalyzerPort,
)
from smb_requirement_agent.analysis.application.ports.requirement_evidence_analyzer import (
    EvidenceFragmentCachePort,
)
from smb_requirement_agent.analysis.application.use_cases.analysis_collaboration import (
    AnalysisCollaboration,
)
from smb_requirement_agent.analysis.application.use_cases.analyze_requirement import (
    AnalyzeRequirement,
)
from smb_requirement_agent.analysis.application.use_cases.clarify_requirement_analysis import (
    ClarifyRequirementAnalysis,
)
from smb_requirement_agent.analysis.application.use_cases.confirm_requirement_analysis import (
    ConfirmRequirementAnalysis,
)
from smb_requirement_agent.analysis.application.use_cases.get_requirement_analysis import (
    GetRequirementAnalysis,
)
from smb_requirement_agent.application.events import InProcessEventDispatcher
from smb_requirement_agent.application.ports.knowledge_index_generations import (
    KnowledgeIndexGenerationsPort,
)
from smb_requirement_agent.application.ports.prior_art import PriorArtStorePort
from smb_requirement_agent.application.ports.requirement_knowledge import (
    RequirementKnowledgeIndexPort,
    RequirementKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.answer_suggestions import (
    SuggestClarificationAnswers,
)
from smb_requirement_agent.application.use_cases.corpus_actions import (
    BulkReindexRequirements,
    ReinstateToCorpus,
    RetireFromCorpus,
)
from smb_requirement_agent.application.use_cases.knowledge_portfolio import (
    KnowledgePortfolio,
    NudgeFindingOwners,
)
from smb_requirement_agent.application.use_cases.prior_art import GetPriorArt, HistoricCitations
from smb_requirement_agent.application.use_cases.rebuild_knowledge_index import (
    RebuildKnowledgeIndex,
)
from smb_requirement_agent.application.use_cases.requirement_indexing import (
    IndexBacklogReader,
    IndexRequirementKnowledge,
)
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    DecideKnowledgeFinding,
    EnsureKnowledgeScreen,
    GetKnowledgeReview,
    ScreenRequirementKnowledge,
)
from smb_requirement_agent.application.use_cases.source_impact import SourceImpactReview
from smb_requirement_agent.application.use_cases.unified_knowledge_search import (
    UnifiedKnowledgeSearch,
)
from smb_requirement_agent.breakdown.application.ports.epic_generator import EpicGeneratorPort
from smb_requirement_agent.breakdown.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.breakdown.application.ports.feature_generator import FeatureGeneratorPort
from smb_requirement_agent.breakdown.application.ports.feature_repository import (
    FeatureRepositoryPort,
)
from smb_requirement_agent.breakdown.application.ports.story_generator import StoryGeneratorPort
from smb_requirement_agent.breakdown.application.ports.story_quality_evaluator import (
    StoryQualityEvaluatorPort,
)
from smb_requirement_agent.breakdown.application.ports.story_quality_repository import (
    StoryQualityRepositoryPort,
)
from smb_requirement_agent.breakdown.application.ports.story_repository import (
    StoryChangeProposalRepositoryPort,
    StoryRepositoryPort,
)
from smb_requirement_agent.breakdown.application.use_cases.architecture_mapping import (
    MapBreakdownArchitecture,
    MapFeatureArchitecture,
    MapStoryArchitecture,
)
from smb_requirement_agent.breakdown.application.use_cases.architecture_mapping_jobs import (
    ArchitectureMappingJobs,
)
from smb_requirement_agent.breakdown.application.use_cases.edit_epic import EditEpic
from smb_requirement_agent.breakdown.application.use_cases.feature_review import (
    EditFeature,
    GetFeatures,
)
from smb_requirement_agent.breakdown.application.use_cases.generate_epic import GenerateEpic
from smb_requirement_agent.breakdown.application.use_cases.generate_features import GenerateFeatures
from smb_requirement_agent.breakdown.application.use_cases.get_epic import GetEpic
from smb_requirement_agent.breakdown.application.use_cases.story_change_proposals import (
    StoryChangeProposals,
)
from smb_requirement_agent.breakdown.application.use_cases.story_quality import (
    GetFeatureQualitySnapshot,
    SuggestStorySplit,
    ValidateFeatureStories,
    ValidateStory,
)
from smb_requirement_agent.breakdown.application.use_cases.story_workflow import (
    EditStory,
    GenerateStories,
    GetStories,
    MergeStories,
    RegenerateStory,
    SplitStory,
)
from smb_requirement_agent.governance.application.exports import ExportFormat
from smb_requirement_agent.governance.application.ports.backlog_export import BacklogExportPort
from smb_requirement_agent.governance.application.ports.breakdown_repository import (
    BreakdownRepositoryPort,
)
from smb_requirement_agent.governance.application.ports.breakdown_review_repository import (
    BreakdownReviewRepositoryPort,
)
from smb_requirement_agent.governance.application.use_cases.approval_workflow import (
    AddReviewComment,
    ApproveBreakdown,
    ApproveStory,
    GetApprovalWorkflow,
    RejectStory,
    SubmitForReview,
)
from smb_requirement_agent.governance.application.use_cases.approve_epic import ApproveEpic
from smb_requirement_agent.governance.application.use_cases.approve_feature import ApproveFeature
from smb_requirement_agent.governance.application.use_cases.breakdown_review import (
    GenerateBreakdownReview,
    GetBreakdownReview,
    RecordDecision,
    ResolveFlag,
    ResolveOpenQuestion,
)
from smb_requirement_agent.governance.application.use_cases.export_breakdown import ExportBreakdown
from smb_requirement_agent.governance.application.use_cases.revision_history import (
    CompareBreakdownVersions,
    GetRevisionHistory,
)
from smb_requirement_agent.governance.infrastructure.exports.json_exporter import (
    JsonBacklogExporter,
)
from smb_requirement_agent.governance.infrastructure.exports.xlsx_exporter import (
    XlsxBacklogExporter,
)
from smb_requirement_agent.identity.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.identity.application.ports.actor_directory import ActorDirectoryPort
from smb_requirement_agent.infrastructure.config.settings import (
    Settings,
)
from smb_requirement_agent.infrastructure.jobs.requirement_index_worker import (
    RequirementIndexWorker,
)
from smb_requirement_agent.interfaces.api.composition.analysis import (
    build_analysis_workflow,
    build_requirement_analyzer,
)
from smb_requirement_agent.interfaces.api.composition.breakdown import (
    BreakdownModels,
    build_architecture_jobs,
    build_breakdown,
)
from smb_requirement_agent.interfaces.api.composition.events import (
    subscribe_domain_event_handlers,
)
from smb_requirement_agent.interfaces.api.composition.governance import build_review
from smb_requirement_agent.interfaces.api.composition.identity import build_identity
from smb_requirement_agent.interfaces.api.composition.jobs import build_ai_jobs
from smb_requirement_agent.interfaces.api.composition.knowledge import build_requirement_knowledge
from smb_requirement_agent.interfaces.api.composition.knowledge_service import (
    KnowledgeService,
    build_backlog_handoff_worker,
    build_knowledge_service,
)
from smb_requirement_agent.interfaces.api.composition.llm import build_llm_adapters
from smb_requirement_agent.interfaces.api.composition.persistence import build_persistence
from smb_requirement_agent.interfaces.api.composition.requirements import (
    build_documents,
    build_requirement_intake,
)
from smb_requirement_agent.jobs.application.ports.ai_jobs import (
    AiJobQueuePort,
    AiJobRepositoryPort,
    AiJobWorkerPort,
)
from smb_requirement_agent.jobs.application.ports.notifications import NotificationRepositoryPort
from smb_requirement_agent.jobs.application.use_cases.provider_call_rate import (
    ProviderCallRateLimit,
)
from smb_requirement_agent.references.application.ports.architecture_knowledge import (
    ArchitectureKnowledgePort,
)
from smb_requirement_agent.references.application.ports.historic_corpus import HistoricCorpusPort
from smb_requirement_agent.references.application.ports.knowledge_handoff import (
    ApprovedBacklogOutboxPort,
)
from smb_requirement_agent.references.application.use_cases.historic_corpus import (
    IndexHistoricCorpus,
    ProjectHistoricRequirements,
)
from smb_requirement_agent.references.application.use_cases.knowledge_views import KnowledgeViews
from smb_requirement_agent.references.application.use_cases.reference_currency import (
    CurrentArchitectureRelease,
    CurrentReferences,
    ProjectKnowledgeEvents,
    ReferenceCurrency,
)
from smb_requirement_agent.reporting.application.ports.activity import (
    ActivityReadPort,
    ReportingReadPort,
)
from smb_requirement_agent.reporting.application.ports.requirement_worklist import (
    CurrentWorklistProjectionPort,
)
from smb_requirement_agent.reporting.application.ports.saved_views import SavedViewRepositoryPort
from smb_requirement_agent.reporting.application.use_cases.activity_reporting import (
    GetOperationalReport,
    ListActivity,
)
from smb_requirement_agent.reporting.application.use_cases.requirement_worklist import (
    RequirementWorklistReader,
)
from smb_requirement_agent.reporting.application.use_cases.saved_views import SavedViews
from smb_requirement_agent.requirements.application.ports.document_repository import (
    DocumentRepositoryPort,
)
from smb_requirement_agent.requirements.application.ports.requirement_draft_repository import (
    RequirementDraftRepositoryPort,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.application.use_cases.attachment_ingestion import (
    AttachmentIngestion,
)
from smb_requirement_agent.requirements.application.use_cases.documents import (
    GetDocument,
    ListDocuments,
    RemoveDocument,
    SetDocumentInclusion,
    SetHiddenWorksheetInclusion,
    UploadDocument,
)
from smb_requirement_agent.requirements.application.use_cases.get_requirement import GetRequirement
from smb_requirement_agent.requirements.application.use_cases.owned_requirements import (
    CreateOwnedRequirement,
    CreateOwnedRequirementDraft,
    GetOwnedRequirementDraft,
    ListOwnedRequirementDrafts,
    PromoteOwnedRequirementDraft,
    SaveOwnedRequirementDraft,
)
from smb_requirement_agent.requirements.infrastructure.attachment_worker import (
    AttachmentIngestionWorker,
)
from smb_requirement_agent.workflows.application.use_cases.ai_job_execution import ExecuteAiJob
from smb_requirement_agent.workflows.application.use_cases.ai_job_scheduling import (
    AnswerSuggestionScheduler,
    KnowledgeScreenScheduler,
)
from smb_requirement_agent.workflows.application.use_cases.ai_jobs import (
    AiJobs,
    Notifications,
)
from smb_requirement_agent.workflows.application.use_cases.generation_context import (
    GenerationContextTokens,
)
from smb_requirement_agent.workflows.application.use_cases.identity_access import (
    RequirementAccessService,
    ResolveCurrentActor,
    SearchKnownActors,
)
from smb_requirement_agent.workflows.application.use_cases.internal_reads import InternalReads
from smb_requirement_agent.workflows.application.use_cases.requirement_commands import (
    RequirementCommands,
)
from smb_requirement_agent.workflows.application.use_cases.requirement_impact import (
    PreviewRequirementImpact,
    UpdateRequirementWithImpact,
)


class BackgroundWorker(Protocol):
    """A thread-owning component started and stopped with its process."""

    @property
    def healthy(self) -> bool: ...

    def start(self) -> None: ...

    def stop(self) -> bool:
        """Stop and report whether in-flight work drained within its grace period."""
        ...

    def wait_until_stopped(self) -> None: ...


@dataclass(frozen=True)
class Container:
    """A fully wired object graph for one running application."""

    requirement_repository: RequirementRepositoryPort
    access_repository: AccessRepositoryPort
    actor_directory: ActorDirectoryPort
    identity_provider: IdentityProviderPort
    close_resources: Callable[[], None]
    readiness_check: Callable[[], bool]
    settings: Settings
    debug_trace: DebugTrace
    requirement_draft_repository: RequirementDraftRepositoryPort
    document_repository: DocumentRepositoryPort
    document_storage: DocumentStoragePort
    attachment_ingestion: AttachmentIngestion
    source_impact: SourceImpactReview
    internal_reads: InternalReads
    knowledge_portfolio: KnowledgePortfolio
    nudge_finding_owners: NudgeFindingOwners
    retire_from_corpus: RetireFromCorpus
    reinstate_to_corpus: ReinstateToCorpus
    bulk_reindex: BulkReindexRequirements
    knowledge_views: KnowledgeViews
    knowledge_projection: ProjectKnowledgeEvents
    historic_projection: ProjectHistoricRequirements
    historic_indexer: IndexHistoricCorpus
    historic_corpus: HistoricCorpusPort
    prior_art_store: PriorArtStorePort
    current_release: CurrentArchitectureRelease
    unified_knowledge_search: UnifiedKnowledgeSearch
    reference_currency: ReferenceCurrency
    current_references: CurrentReferences
    requirement_indexer: IndexRequirementKnowledge
    requirement_index_worker: RequirementIndexWorker
    attachment_ingestion_worker: AttachmentIngestionWorker
    # Every background worker this process may run, keyed by its readiness check name.
    background_workers: Mapping[str, BackgroundWorker]
    analysis_repository: RequirementAnalysisRepositoryPort
    analysis_audit_repository: AnalysisAuditRepositoryPort
    epic_repository: EpicRepositoryPort
    feature_repository: FeatureRepositoryPort
    story_repository: StoryRepositoryPort
    story_proposal_repository: StoryChangeProposalRepositoryPort
    story_quality_repository: StoryQualityRepositoryPort
    breakdown_review_repository: BreakdownReviewRepositoryPort
    analyzer: RequirementAnalyzerPort
    epic_generator: EpicGeneratorPort
    feature_generator: FeatureGeneratorPort
    story_generator: StoryGeneratorPort
    story_quality_evaluator: StoryQualityEvaluatorPort
    architecture_knowledge: ArchitectureKnowledgePort
    architecture_mapping_jobs: ArchitectureMappingJobs
    clock: ClockPort
    breakdown_repository: BreakdownRepositoryPort
    transaction_manager: TransactionManagerPort
    # Approved backlogs on their way to the knowledge service (ADR-0101 Amendment 2).
    backlog_handoffs: ApprovedBacklogOutboxPort
    ai_job_repository: AiJobRepositoryPort
    ai_job_queue: AiJobQueuePort
    notification_repository: NotificationRepositoryPort
    activity_reader: ActivityReadPort
    reporting_reader: ReportingReadPort
    saved_view_repository: SavedViewRepositoryPort
    backlog_exporters: tuple[BacklogExportPort, ...]
    ai_jobs: AiJobs
    execute_ai_job: ExecuteAiJob
    notifications: Notifications
    list_activity: ListActivity
    get_operational_report: GetOperationalReport
    saved_views: SavedViews
    ai_job_worker: AiJobWorkerPort
    resolve_current_actor: ResolveCurrentActor
    search_known_actors: SearchKnownActors
    requirement_access: RequirementAccessService
    generation_context_tokens: GenerationContextTokens
    requirement_commands: RequirementCommands
    provider_call_rate_limit: ProviderCallRateLimit
    metrics: Metrics
    create_requirement: CreateOwnedRequirement
    get_requirement: GetRequirement
    list_requirement_worklist: RequirementWorklistReader
    worklist_projection: CurrentWorklistProjectionPort
    create_requirement_draft: CreateOwnedRequirementDraft
    get_requirement_draft: GetOwnedRequirementDraft
    list_requirement_drafts: ListOwnedRequirementDrafts
    save_requirement_draft: SaveOwnedRequirementDraft
    promote_requirement_draft: PromoteOwnedRequirementDraft
    upload_document: UploadDocument
    list_documents: ListDocuments
    get_document: GetDocument
    set_document_inclusion: SetDocumentInclusion
    set_hidden_worksheet_inclusion: SetHiddenWorksheetInclusion
    remove_document: RemoveDocument
    preview_requirement_impact: PreviewRequirementImpact
    update_requirement: UpdateRequirementWithImpact
    analyze_requirement: AnalyzeRequirement
    analysis_collaboration: AnalysisCollaboration
    clarify_requirement_analysis: ClarifyRequirementAnalysis
    confirm_requirement_analysis: ConfirmRequirementAnalysis
    get_requirement_analysis: GetRequirementAnalysis
    generate_epic: GenerateEpic
    get_epic: GetEpic
    edit_epic: EditEpic
    approve_epic: ApproveEpic
    generate_features: GenerateFeatures
    get_features: GetFeatures
    edit_feature: EditFeature
    approve_feature: ApproveFeature
    approve_story: ApproveStory
    reject_story: RejectStory
    generate_stories: GenerateStories
    get_stories: GetStories
    edit_story: EditStory
    split_story: SplitStory
    merge_stories: MergeStories
    regenerate_story: RegenerateStory
    story_change_proposals: StoryChangeProposals
    validate_story: ValidateStory
    validate_feature_stories: ValidateFeatureStories
    get_feature_quality_snapshot: GetFeatureQualitySnapshot
    suggest_story_split: SuggestStorySplit
    map_feature_architecture: MapFeatureArchitecture
    map_story_architecture: MapStoryArchitecture
    map_breakdown_architecture: MapBreakdownArchitecture
    generate_breakdown_review: GenerateBreakdownReview
    get_breakdown_review: GetBreakdownReview
    record_decision: RecordDecision
    resolve_flag: ResolveFlag
    resolve_open_question: ResolveOpenQuestion
    get_approval_workflow: GetApprovalWorkflow
    submit_for_review: SubmitForReview
    approve_breakdown: ApproveBreakdown
    add_review_comment: AddReviewComment
    get_revision_history: GetRevisionHistory
    compare_breakdown_versions: CompareBreakdownVersions
    export_breakdown: ExportBreakdown
    knowledge_index: RequirementKnowledgeIndexPort
    knowledge_repository: RequirementKnowledgeRepositoryPort
    evidence_fragment_cache: EvidenceFragmentCachePort
    screen_requirement_knowledge: ScreenRequirementKnowledge
    get_knowledge_review: GetKnowledgeReview
    get_prior_art: GetPriorArt
    historic_citations: HistoricCitations
    ensure_knowledge_screen: EnsureKnowledgeScreen
    decide_knowledge_finding: DecideKnowledgeFinding
    suggest_clarification_answers: SuggestClarificationAnswers
    knowledge_scheduler: KnowledgeScreenScheduler
    answer_suggestion_scheduler: AnswerSuggestionScheduler
    knowledge_index_generations: KnowledgeIndexGenerationsPort | None
    rebuild_knowledge_index: RebuildKnowledgeIndex | None


def build_container(
    settings: Settings | None = None,
    *,
    analyzer: RequirementAnalyzerPort | None = None,
    epic_generator: EpicGeneratorPort | None = None,
    feature_generator: FeatureGeneratorPort | None = None,
    story_generator: StoryGeneratorPort | None = None,
    story_quality_evaluator: StoryQualityEvaluatorPort | None = None,
    architecture_knowledge: ArchitectureKnowledgePort | None = None,
    clock: ClockPort | None = None,
    identity_provider: IdentityProviderPort | None = None,
    knowledge_service: KnowledgeService | None = None,
) -> Container:
    with ExitStack() as resources:
        container = _build_container(
            settings,
            analyzer=analyzer,
            epic_generator=epic_generator,
            feature_generator=feature_generator,
            story_generator=story_generator,
            story_quality_evaluator=story_quality_evaluator,
            architecture_knowledge=architecture_knowledge,
            clock=clock,
            identity_provider=identity_provider,
            knowledge_service=knowledge_service,
            resources=resources,
        )
        owned = resources.pop_all()
        return replace(container, close_resources=owned.close)


def _build_container(
    settings: Settings | None = None,
    *,
    analyzer: RequirementAnalyzerPort | None = None,
    epic_generator: EpicGeneratorPort | None = None,
    feature_generator: FeatureGeneratorPort | None = None,
    story_generator: StoryGeneratorPort | None = None,
    story_quality_evaluator: StoryQualityEvaluatorPort | None = None,
    architecture_knowledge: ArchitectureKnowledgePort | None = None,
    clock: ClockPort | None = None,
    identity_provider: IdentityProviderPort | None = None,
    knowledge_service: KnowledgeService | None = None,
    resources: ExitStack,
) -> Container:
    """Wire the object graph.

    The keyword arguments let a caller substitute a double without going
    through the environment; everything else follows from `settings`.
    """
    settings = settings if settings is not None else Settings.from_env()
    resolved_clock = clock if clock is not None else SystemClock()
    backlog_exporters: tuple[BacklogExportPort, ...] = (
        JsonBacklogExporter(),
        XlsxBacklogExporter(),
    )
    metrics = Metrics()
    defaults = build_llm_adapters(settings, metrics)
    resources.callback(defaults.close)
    resources.callback(defaults.debug_trace.close)
    persistence = build_persistence(settings, resources, resolved_clock)
    # Tests may supply their own knowledge service; otherwise settings choose it.
    knowledge_service = knowledge_service or build_knowledge_service(settings, resources, metrics)
    resolved_identity = build_identity(
        settings, resources, persistence.actor_directory, identity_provider
    )
    resolved_analyzer = (
        analyzer
        if analyzer is not None
        else build_requirement_analyzer(settings, defaults, persistence, resolved_clock)
    )
    resolved_generator = epic_generator if epic_generator is not None else defaults.epic_generator
    resolved_feature_generator = (
        feature_generator if feature_generator is not None else defaults.feature_generator
    )
    resolved_story_generator = (
        story_generator if story_generator is not None else defaults.story_generator
    )
    resolved_story_quality_evaluator = (
        story_quality_evaluator
        if story_quality_evaluator is not None
        else defaults.story_quality_evaluator
    )
    # Architecture matching is the knowledge service's; tests may supply their own.
    resolved_architecture = (
        architecture_knowledge
        if architecture_knowledge is not None
        else knowledge_service.architecture
    )

    domain_events = InProcessEventDispatcher(persistence.transaction_manager)
    subscribe_domain_event_handlers(
        domain_events,
        analyses=persistence.analysis_repository,
        audits=persistence.analysis_audit_repository,
        epics=persistence.epic_repository,
        features=persistence.feature_repository,
        stories=persistence.story_repository,
        reviews=persistence.breakdown_review_repository,
        clock=resolved_clock,
    )
    access_service = RequirementAccessService(
        persistence.requirement_repository,
        persistence.requirement_draft_repository,
        persistence.access_repository,
        persistence.actor_directory,
        resolved_clock,
        persistence.transaction_manager,
        persistence.analysis_audit_repository,
    )
    knowledge = build_requirement_knowledge(
        settings, persistence, defaults, resolved_clock, access_service, knowledge_service
    )
    documents = build_documents(
        settings,
        persistence,
        resolved_clock,
        domain_events,
        access_service,
    )
    worklist = persistence.worklist(knowledge.review)
    intake = build_requirement_intake(
        persistence, resolved_clock, access_service, domain_events, knowledge.screen_scheduler
    )
    analysis = build_analysis_workflow(
        persistence,
        resolved_analyzer,
        documents.analysis_documents,
        knowledge,
        defaults.reference_proposer,
        resolved_clock,
        access_service,
    )
    review = build_review(
        persistence,
        resolved_clock,
        access_service,
        knowledge.source_impact,
        backlog_exporters,
        knowledge.current_release,
        # Approvals hand their backlog over only when there is an inbox to deliver to.
        persistence.backlog_handoffs if knowledge_service.change_requests is not None else None,
    )
    breakdown = build_breakdown(
        persistence,
        BreakdownModels(
            resolved_generator,
            resolved_feature_generator,
            resolved_story_generator,
            resolved_story_quality_evaluator,
        ),
        resolved_architecture,
        review,
        analysis.analysis_collaboration,
        analysis.generation_context_tokens,
        domain_events,
        resolved_clock,
        access_service,
    )
    architecture_jobs = build_architecture_jobs(
        settings,
        persistence,
        breakdown.map_breakdown_architecture,
        resolved_clock,
        knowledge.current_release,
    )
    jobs = build_ai_jobs(
        settings,
        persistence,
        analysis,
        breakdown,
        knowledge,
        resolved_clock,
        access_service,
        metrics,
    )

    background_workers: dict[str, BackgroundWorker] = {
        "requirement_index_worker": knowledge.index_worker,
        "workers": jobs.worker,
        "attachment_worker": documents.attachment_worker,
        "knowledge_event_worker": knowledge.knowledge_event_worker,
        "historic_event_worker": knowledge.historic_event_worker,
        "historic_index_worker": knowledge.historic_index_worker,
    }
    if architecture_jobs.mapping_worker is not None:
        background_workers["architecture_mapping_job_worker"] = architecture_jobs.mapping_worker
    if knowledge_service.change_requests is not None:
        background_workers["approved_backlog_worker"] = build_backlog_handoff_worker(
            persistence,
            next(item for item in backlog_exporters if item.format is ExportFormat.JSON),
            knowledge_service.change_requests,
            resolved_clock,
            metrics,
        )

    backlog = IndexBacklogReader(
        persistence.knowledge_index,
        persistence.requirement_index_progress,
        knowledge.indexer.identity,
        persistence.corpus_membership,
    )
    corpus_action_ports = (
        persistence.requirement_repository,
        persistence.access_repository,
        persistence.knowledge_repository,
        persistence.corpus_membership,
        persistence.corpus_actions,
        persistence.notification_repository,
        persistence.transaction_manager,
        resolved_clock,
    )
    return Container(
        requirement_repository=persistence.requirement_repository,
        access_repository=persistence.access_repository,
        actor_directory=persistence.actor_directory,
        identity_provider=resolved_identity,
        settings=settings,
        debug_trace=defaults.debug_trace,
        close_resources=resources.close,
        readiness_check=persistence.readiness_check,
        requirement_draft_repository=persistence.requirement_draft_repository,
        document_repository=persistence.document_repository,
        document_storage=persistence.document_storage,
        attachment_ingestion=documents.attachment_ingestion,
        source_impact=knowledge.source_impact,
        knowledge_views=KnowledgeViews(knowledge_service.views),
        knowledge_projection=knowledge.projection,
        historic_projection=knowledge.historic_projection,
        historic_indexer=knowledge.historic_indexer,
        historic_corpus=persistence.historic_corpus,
        prior_art_store=persistence.prior_art,
        current_release=knowledge.current_release,
        internal_reads=InternalReads(
            persistence.dependency_index,
            knowledge.source_impact,
            persistence.architecture_mapping_stats,
            persistence.transaction_manager,
            persistence.corpus_counts,
            backlog,
            resolved_clock,
        ),
        knowledge_portfolio=KnowledgePortfolio(
            persistence.knowledge_portfolio, backlog, resolved_clock
        ),
        retire_from_corpus=RetireFromCorpus(*corpus_action_ports),
        reinstate_to_corpus=ReinstateToCorpus(*corpus_action_ports),
        bulk_reindex=BulkReindexRequirements(
            backlog,
            persistence.source_changes,
            persistence.corpus_actions,
            persistence.transaction_manager,
            resolved_clock,
        ),
        nudge_finding_owners=NudgeFindingOwners(
            persistence.knowledge_repository,
            persistence.requirement_repository,
            persistence.access_repository,
            persistence.notification_repository,
            persistence.finding_nudges,
            persistence.transaction_manager,
            resolved_clock,
        ),
        unified_knowledge_search=knowledge.unified_search,
        reference_currency=knowledge.reference_currency,
        current_references=knowledge.current_references,
        requirement_indexer=knowledge.indexer,
        requirement_index_worker=knowledge.index_worker,
        attachment_ingestion_worker=documents.attachment_worker,
        background_workers=background_workers,
        analysis_repository=persistence.analysis_repository,
        analysis_audit_repository=persistence.analysis_audit_repository,
        epic_repository=persistence.epic_repository,
        feature_repository=persistence.feature_repository,
        story_repository=persistence.story_repository,
        story_proposal_repository=persistence.story_proposal_repository,
        breakdown_review_repository=persistence.breakdown_review_repository,
        analyzer=resolved_analyzer,
        epic_generator=resolved_generator,
        feature_generator=resolved_feature_generator,
        story_generator=resolved_story_generator,
        story_quality_evaluator=resolved_story_quality_evaluator,
        architecture_knowledge=resolved_architecture,
        architecture_mapping_jobs=architecture_jobs.mapping_jobs,
        clock=resolved_clock,
        breakdown_repository=persistence.revision_repository,
        transaction_manager=persistence.transaction_manager,
        backlog_handoffs=persistence.backlog_handoffs,
        ai_job_repository=persistence.ai_job_repository,
        ai_job_queue=persistence.ai_job_queue,
        notification_repository=persistence.notification_repository,
        activity_reader=persistence.activity_reader,
        reporting_reader=persistence.reporting_reader,
        saved_view_repository=persistence.saved_view_repository,
        backlog_exporters=backlog_exporters,
        story_quality_repository=persistence.story_quality_repository,
        ai_jobs=jobs.ai_jobs,
        execute_ai_job=jobs.execute_ai_job,
        notifications=jobs.notifications,
        list_activity=ListActivity(persistence.activity_reader),
        get_operational_report=GetOperationalReport(
            persistence.activity_reader, persistence.reporting_reader, resolved_clock
        ),
        saved_views=SavedViews(persistence.saved_view_repository, resolved_clock),
        ai_job_worker=jobs.worker,
        resolve_current_actor=ResolveCurrentActor(resolved_identity, persistence.actor_directory),
        search_known_actors=SearchKnownActors(persistence.actor_directory),
        requirement_access=access_service,
        generation_context_tokens=analysis.generation_context_tokens,
        requirement_commands=analysis.requirement_commands,
        metrics=metrics,
        provider_call_rate_limit=ProviderCallRateLimit(
            settings.provider_rate_limit_per_minute, resolved_clock
        ),
        create_requirement=intake.create_requirement,
        get_requirement=intake.get_requirement,
        list_requirement_worklist=worklist.reader,
        worklist_projection=worklist.projection,
        create_requirement_draft=intake.create_requirement_draft,
        get_requirement_draft=intake.get_requirement_draft,
        list_requirement_drafts=intake.list_requirement_drafts,
        save_requirement_draft=intake.save_requirement_draft,
        promote_requirement_draft=intake.promote_requirement_draft,
        upload_document=documents.upload,
        list_documents=documents.list_documents,
        get_document=documents.get_document,
        set_document_inclusion=documents.set_inclusion,
        set_hidden_worksheet_inclusion=documents.set_hidden_worksheet_inclusion,
        remove_document=documents.remove,
        preview_requirement_impact=intake.preview_requirement_impact,
        update_requirement=intake.update_requirement,
        analyze_requirement=analysis.analyze_requirement,
        analysis_collaboration=analysis.analysis_collaboration,
        clarify_requirement_analysis=analysis.clarify_requirement_analysis,
        confirm_requirement_analysis=analysis.confirm_requirement_analysis,
        get_requirement_analysis=analysis.get_requirement_analysis,
        generate_epic=breakdown.generate_epic,
        get_epic=breakdown.get_epic,
        edit_epic=breakdown.edit_epic,
        approve_epic=breakdown.approve_epic,
        generate_features=breakdown.generate_features,
        get_features=breakdown.get_features,
        edit_feature=breakdown.edit_feature,
        approve_feature=breakdown.approve_feature,
        approve_story=breakdown.approve_story,
        reject_story=breakdown.reject_story,
        generate_stories=breakdown.generate_stories,
        get_stories=breakdown.get_stories,
        edit_story=breakdown.edit_story,
        split_story=breakdown.split_story,
        merge_stories=breakdown.merge_stories,
        regenerate_story=breakdown.regenerate_story,
        story_change_proposals=breakdown.story_change_proposals,
        validate_story=breakdown.validate_story,
        validate_feature_stories=breakdown.validate_feature_stories,
        get_feature_quality_snapshot=breakdown.get_feature_quality_snapshot,
        suggest_story_split=breakdown.suggest_story_split,
        map_feature_architecture=breakdown.map_feature_architecture,
        map_story_architecture=breakdown.map_story_architecture,
        map_breakdown_architecture=breakdown.map_breakdown_architecture,
        generate_breakdown_review=breakdown.generate_breakdown_review,
        get_breakdown_review=review.get_breakdown_review,
        record_decision=review.record_decision,
        resolve_flag=review.resolve_flag,
        resolve_open_question=breakdown.resolve_open_question,
        get_approval_workflow=review.get_approval_workflow,
        submit_for_review=review.submit_for_review,
        approve_breakdown=review.approve_breakdown,
        add_review_comment=review.add_review_comment,
        get_revision_history=review.get_revision_history,
        compare_breakdown_versions=review.compare_breakdown_versions,
        export_breakdown=review.export_breakdown,
        knowledge_index=persistence.knowledge_index,
        knowledge_index_generations=persistence.index_generations,
        rebuild_knowledge_index=knowledge.rebuild_index,
        knowledge_repository=persistence.knowledge_repository,
        evidence_fragment_cache=persistence.evidence_fragment_cache,
        screen_requirement_knowledge=knowledge.screen,
        get_knowledge_review=knowledge.review,
        get_prior_art=knowledge.get_prior_art,
        historic_citations=knowledge.historic_citations,
        ensure_knowledge_screen=knowledge.ensure_screen,
        decide_knowledge_finding=knowledge.decide_finding,
        suggest_clarification_answers=knowledge.suggest_answers,
        knowledge_scheduler=knowledge.screen_scheduler,
        answer_suggestion_scheduler=knowledge.answer_scheduler,
    )
