"""Requirement knowledge: the corpus, its index, screening, reference sources and search."""

from __future__ import annotations

from dataclasses import dataclass

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.use_cases.reference_staleness import (
    AnalysisReferenceCurrency,
)
from smb_requirement_agent.application.use_cases.answer_suggestions import (
    SuggestClarificationAnswers,
)
from smb_requirement_agent.application.use_cases.prior_art import (
    GetPriorArt,
    HistoricCitations,
    PriorArtScheduler,
    ScreenPriorArt,
)
from smb_requirement_agent.application.use_cases.rebuild_knowledge_index import (
    RebuildKnowledgeIndex,
)
from smb_requirement_agent.application.use_cases.requirement_indexing import (
    IndexRequirementKnowledge,
)
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    DecideKnowledgeFinding,
    EnsureKnowledgeScreen,
    GetKnowledgeReview,
    RequirementKnowledgeCorpus,
    ScreenRequirementKnowledge,
)
from smb_requirement_agent.application.use_cases.source_impact import SourceImpactReview
from smb_requirement_agent.application.use_cases.unified_knowledge_search import (
    UnifiedKnowledgeSearch,
)
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.documents.ingestion_loop import IngestionLoop
from smb_requirement_agent.infrastructure.jobs.requirement_index_worker import (
    RequirementIndexWorker,
)
from smb_requirement_agent.interfaces.api.composition.knowledge_service import KnowledgeService
from smb_requirement_agent.interfaces.api.composition.llm import LLMAdapters
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters
from smb_requirement_agent.references.application.ports.reference_grounding import (
    ReferenceKnowledgePort,
)
from smb_requirement_agent.references.application.use_cases.historic_corpus import (
    IndexHistoricCorpus,
    ProjectHistoricRequirements,
    historic_identity,
)
from smb_requirement_agent.references.application.use_cases.reference_currency import (
    CurrentArchitectureRelease,
    CurrentReferences,
    ProjectKnowledgeEvents,
    ReferenceCurrency,
)
from smb_requirement_agent.references.infrastructure.knowledge_payloads import (
    PayloadKnowledgeStateDecoder,
)
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
)
from smb_requirement_agent.workflows.application.use_cases.ai_job_scheduling import (
    AnswerSuggestionScheduler,
    KnowledgeScreenScheduler,
)
from smb_requirement_agent.workflows.application.use_cases.identity_access import (
    RequirementAccessService,
)

# The actor recorded on jobs the system schedules for itself.
_AUTOMATIC_ACTOR = ActorProfile(
    ActorId("system:requirement-knowledge"), "Automatic requirement knowledge"
)


@dataclass(frozen=True)
class RequirementKnowledgeWiring:
    corpus: RequirementKnowledgeCorpus
    review: GetKnowledgeReview
    # Only a generation-aware index with configured profiles can be rebuilt.
    rebuild_index: RebuildKnowledgeIndex | None
    screen_scheduler: KnowledgeScreenScheduler
    answer_scheduler: AnswerSuggestionScheduler
    indexer: IndexRequirementKnowledge
    index_worker: RequirementIndexWorker
    # What requirement work searches and cites: the knowledge service's library.
    references: ReferenceKnowledgePort
    reference_currency: ReferenceCurrency
    current_references: CurrentReferences
    current_release: CurrentArchitectureRelease
    knowledge_event_worker: IngestionLoop
    # Brings the local copies up to date with the knowledge service's events.
    projection: ProjectKnowledgeEvents
    source_impact: SourceImpactReview
    suggest_answers: SuggestClarificationAnswers
    screen: ScreenRequirementKnowledge
    ensure_screen: EnsureKnowledgeScreen
    decide_finding: DecideKnowledgeFinding
    unified_search: UnifiedKnowledgeSearch
    # Historic requirements (Knowledge Center E2, ADR-0102): their own cursor, their own
    # loops, so a slow page of historic content never holds up reference currency.
    # Prior art from the historic corpus: informational, never a finding.
    get_prior_art: GetPriorArt
    screen_prior_art: ScreenPriorArt
    historic_citations: HistoricCitations
    historic_projection: ProjectHistoricRequirements
    historic_event_worker: IngestionLoop
    historic_indexer: IndexHistoricCorpus
    historic_index_worker: IngestionLoop


def build_requirement_knowledge(
    settings: Settings,
    persistence: PersistenceAdapters,
    llm: LLMAdapters,
    clock: ClockPort,
    access: RequirementAccessService,
    service: KnowledgeService,
) -> RequirementKnowledgeWiring:
    embedding_identity = _embedding_identity(settings)
    corpus = RequirementKnowledgeCorpus(
        persistence.requirement_repository,
        persistence.analysis_repository,
        persistence.analysis_audit_repository,
        persistence.access_repository,
        persistence.knowledge_repository,
        persistence.document_repository,
        membership=persistence.corpus_membership,
    )
    review = GetKnowledgeReview(corpus, persistence.knowledge_repository)
    historic_index_identity = historic_identity(embedding_identity)
    get_prior_art = GetPriorArt(
        corpus,
        persistence.historic_corpus,
        persistence.historic_corpus,
        persistence.prior_art,
        persistence.ai_job_repository,
        persistence.prior_art,
        clock,
        identity=historic_index_identity,
        enabled=settings.prior_art_enabled,
        judge_calls_per_hour=settings.prior_art_judge_calls_per_hour,
    )
    prior_art_scheduler = PriorArtScheduler(
        get_prior_art,
        persistence.prior_art,
        persistence.historic_corpus,
        persistence.ai_job_repository,
        persistence.requirement_repository,
        clock,
        _AUTOMATIC_ACTOR,
        identity=historic_index_identity,
        enabled=settings.prior_art_enabled,
    )
    screen_scheduler = KnowledgeScreenScheduler(
        review,
        persistence.ai_job_repository,
        persistence.requirement_repository,
        persistence.knowledge_repository,
        clock,
        _AUTOMATIC_ACTOR,
        membership=persistence.corpus_membership,
        prior_art=prior_art_scheduler,
    )
    indexer = IndexRequirementKnowledge(
        corpus,
        persistence.knowledge_index,
        llm.knowledge_embedding,
        persistence.requirement_index_progress,
        clock,
        embedding_identity,
        access,
    )
    # Requirement work checks citations against its local copy of the library's state.
    reference_currency = ReferenceCurrency(
        persistence.reference_publications, persistence.transaction_manager
    )
    references = service.references
    current_references = CurrentReferences(references, reference_currency)
    knowledge_states = PayloadKnowledgeStateDecoder()
    projector = ProjectKnowledgeEvents(
        service.events,
        persistence.reference_publications,
        persistence.architecture_releases,
        persistence.transaction_manager,
        clock,
        decoder=knowledge_states,
    )
    historic_projector = ProjectHistoricRequirements(
        service.events,
        persistence.historic_corpus,
        persistence.historic_corpus,
        persistence.transaction_manager,
        clock,
        decoder=knowledge_states,
    )
    historic_indexer = IndexHistoricCorpus(
        service.historic_content,
        persistence.historic_corpus,
        llm.knowledge_embedding,
        clock,
        historic_index_identity,
        settings.historic_embed_chunks_per_hour,
    )
    if not service.remote:
        # The offline feed is fixed; read it now so a catalogue version is known at once.
        # A remote service's events are polled by the knowledge event worker instead.
        projector.drain()
        historic_projector.drain()
    return RequirementKnowledgeWiring(
        corpus=corpus,
        review=review,
        rebuild_index=RebuildKnowledgeIndex(
            corpus,
            llm.knowledge_embedding,
            persistence.index_generations,
            settings.llm_profiles.selected_embedding.identity,
        )
        if persistence.index_generations is not None and settings.llm_profiles is not None
        else None,
        screen_scheduler=screen_scheduler,
        answer_scheduler=AnswerSuggestionScheduler(
            persistence.ai_job_repository, clock, _AUTOMATIC_ACTOR
        ),
        indexer=indexer,
        index_worker=RequirementIndexWorker(indexer),
        references=references,
        reference_currency=reference_currency,
        current_references=current_references,
        current_release=CurrentArchitectureRelease(persistence.architecture_releases),
        knowledge_event_worker=IngestionLoop("knowledge-events", (projector.project_next,)),
        projection=projector,
        source_impact=SourceImpactReview(
            persistence.dependency_index,
            persistence.reference_publications,
            access,
            persistence.transaction_manager,
            clock,
            AnalysisReferenceCurrency(reference_currency, persistence.transaction_manager),
        ),
        suggest_answers=SuggestClarificationAnswers(
            persistence.requirement_repository,
            persistence.analysis_audit_repository,
            persistence.access_repository,
            corpus,
            persistence.knowledge_index,
            persistence.knowledge_repository,
            llm.knowledge_embedding,
            llm.answer_suggester,
            clock,
            persistence.transaction_manager,
            current_references,
            authorization=access,
        ),
        screen=ScreenRequirementKnowledge(
            persistence.requirement_repository,
            corpus,
            persistence.knowledge_index,
            persistence.knowledge_repository,
            llm.knowledge_embedding,
            llm.relationship_classifier,
            clock,
            persistence.transaction_manager,
            authorization=access,
        ),
        ensure_screen=EnsureKnowledgeScreen(
            persistence.requirement_repository,
            access,
            screen_scheduler,
        ),
        decide_finding=DecideKnowledgeFinding(
            persistence.requirement_repository,
            persistence.access_repository,
            persistence.knowledge_repository,
            clock,
            persistence.transaction_manager,
            screen_scheduler,
            authorization=access,
            membership=persistence.corpus_membership,
        ),
        get_prior_art=get_prior_art,
        screen_prior_art=ScreenPriorArt(
            persistence.requirement_repository,
            corpus,
            persistence.historic_corpus,
            persistence.historic_corpus,
            persistence.prior_art,
            llm.knowledge_embedding,
            llm.prior_art_judge,
            persistence.prior_art,
            clock,
            persistence.transaction_manager,
            authorization=access,
            identity=historic_index_identity,
            enabled=settings.prior_art_enabled,
            judge_calls_per_hour=settings.prior_art_judge_calls_per_hour,
        ),
        historic_citations=HistoricCitations(
            persistence.prior_art,
            get_prior_art,
            persistence.requirement_repository,
            persistence.access_repository,
            corpus,
        ),
        historic_projection=historic_projector,
        historic_event_worker=IngestionLoop(
            "historic-requirements", (historic_projector.project_next,)
        ),
        historic_indexer=historic_indexer,
        historic_index_worker=IngestionLoop("historic-index", (historic_indexer.process_next,)),
        unified_search=UnifiedKnowledgeSearch(
            corpus,
            persistence.knowledge_index,
            llm.knowledge_embedding,
            current_references,
            persistence.access_repository,
        ),
    )


def _embedding_identity(settings: Settings) -> str:
    """Which embedding space stored vectors belong to; a change forces re-indexing."""
    if settings.llm_profiles:
        return str(settings.llm_profiles.selected_embedding.identity)
    return (
        f"{settings.llm_provider.value}:{settings.openai_embedding_model}:"
        f"{settings.local_embedding_model}:"
        f"{settings.local_llm_base_url}:{settings.openrouter_embedding_model}:"
        f"{settings.openrouter_base_url}"
    )
