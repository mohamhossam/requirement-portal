"""Requirement knowledge: the corpus, its index, screening, reference sources and search."""

from __future__ import annotations

from dataclasses import dataclass

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.use_cases.ai_job_scheduling import (
    AnswerSuggestionScheduler,
    KnowledgeScreenScheduler,
)
from smb_requirement_agent.application.use_cases.answer_suggestions import (
    SuggestClarificationAnswers,
)
from smb_requirement_agent.application.use_cases.identity_access import RequirementAccessService
from smb_requirement_agent.application.use_cases.rebuild_knowledge_index import (
    RebuildKnowledgeIndex,
)
from smb_requirement_agent.application.use_cases.reference_knowledge import (
    ReferenceKnowledge,
    StructureAwareChunks,
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
from smb_requirement_agent.domain.identity.entities import ActorId, ActorProfile
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.jobs.requirement_index_worker import (
    RequirementIndexWorker,
)
from smb_requirement_agent.infrastructure.persistence.reference_index import Utf8BudgetCounter
from smb_requirement_agent.interfaces.api.composition.llm import LLMAdapters
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters

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
    reference_knowledge: ReferenceKnowledge
    source_impact: SourceImpactReview
    suggest_answers: SuggestClarificationAnswers
    screen: ScreenRequirementKnowledge
    ensure_screen: EnsureKnowledgeScreen
    decide_finding: DecideKnowledgeFinding
    unified_search: UnifiedKnowledgeSearch


def build_requirement_knowledge(
    settings: Settings,
    persistence: PersistenceAdapters,
    llm: LLMAdapters,
    clock: ClockPort,
    access: RequirementAccessService,
) -> RequirementKnowledgeWiring:
    embedding_identity = _embedding_identity(settings)
    corpus = RequirementKnowledgeCorpus(
        persistence.requirement_repository,
        persistence.analysis_repository,
        persistence.analysis_audit_repository,
        persistence.access_repository,
        persistence.knowledge_repository,
    )
    review = GetKnowledgeReview(corpus, persistence.knowledge_repository)
    screen_scheduler = KnowledgeScreenScheduler(
        review,
        persistence.ai_job_repository,
        persistence.requirement_repository,
        persistence.knowledge_repository,
        clock,
        _AUTOMATIC_ACTOR,
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
    reference_knowledge = ReferenceKnowledge(
        persistence.library_repository,
        persistence.reference_index,
        llm.knowledge_embedding,
        StructureAwareChunks(Utf8BudgetCounter()),
        persistence.transaction_manager,
        clock,
        embedding_identity,
    )
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
        reference_knowledge=reference_knowledge,
        source_impact=SourceImpactReview(
            persistence.dependency_index,
            persistence.library_repository,
            access,
            persistence.transaction_manager,
            clock,
            reference_knowledge,
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
            reference_knowledge,
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
        ),
        unified_search=UnifiedKnowledgeSearch(
            corpus,
            persistence.knowledge_index,
            llm.knowledge_embedding,
            reference_knowledge,
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
