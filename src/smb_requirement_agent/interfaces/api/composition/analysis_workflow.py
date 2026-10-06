"""The analysis workflow around the analyzer: generation, clarification and confirmation.

It also owns the generation-context tokens, which every model-backed action
checks, so a person only acts on the context they were shown.
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.reference_grounding import ReferenceProposerPort
from smb_requirement_agent.application.ports.requirement_analyzer import RequirementAnalyzerPort
from smb_requirement_agent.application.use_cases.analysis_collaboration import (
    AnalysisCollaboration,
)
from smb_requirement_agent.application.use_cases.analyze_requirement import AnalyzeRequirement
from smb_requirement_agent.application.use_cases.clarify_requirement_analysis import (
    ClarifyRequirementAnalysis,
)
from smb_requirement_agent.application.use_cases.confirm_requirement_analysis import (
    ConfirmRequirementAnalysis,
)
from smb_requirement_agent.application.use_cases.documents import AssembleAnalysisDocuments
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.application.use_cases.get_requirement_analysis import (
    GetRequirementAnalysis,
)
from smb_requirement_agent.application.use_cases.identity_access import RequirementAccessService
from smb_requirement_agent.application.use_cases.reference_grounding import ReferenceGrounding
from smb_requirement_agent.application.use_cases.requirement_commands import RequirementCommands
from smb_requirement_agent.infrastructure.text.budget import Utf8BudgetCounter
from smb_requirement_agent.interfaces.api.composition.knowledge import RequirementKnowledgeWiring
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters


@dataclass(frozen=True)
class AnalysisWorkflowWiring:
    generation_context_tokens: GenerationContextTokens
    requirement_commands: RequirementCommands
    analysis_collaboration: AnalysisCollaboration
    analyze_requirement: AnalyzeRequirement
    clarify_requirement_analysis: ClarifyRequirementAnalysis
    confirm_requirement_analysis: ConfirmRequirementAnalysis
    get_requirement_analysis: GetRequirementAnalysis


def build_analysis_workflow(
    persistence: PersistenceAdapters,
    analyzer: RequirementAnalyzerPort,
    analysis_documents: AssembleAnalysisDocuments,
    knowledge: RequirementKnowledgeWiring,
    reference_proposer: ReferenceProposerPort,
    clock: ClockPort,
    access: RequirementAccessService,
) -> AnalysisWorkflowWiring:
    contexts = GenerationContextTokens(
        persistence.requirement_repository,
        persistence.analysis_repository,
        persistence.analysis_audit_repository,
        persistence.document_repository,
        persistence.epic_repository,
        persistence.feature_repository,
        persistence.story_repository,
        persistence.story_proposal_repository,
        transactions=persistence.transaction_manager,
        references=knowledge.source_impact,
    )
    collaboration = AnalysisCollaboration(
        persistence.requirement_repository,
        persistence.analysis_repository,
        persistence.analysis_audit_repository,
        analyzer,
        analysis_documents,
        persistence.access_repository,
        persistence.actor_directory,
        clock,
        persistence.transaction_manager,
        knowledge.screen_scheduler,
        knowledge.answer_scheduler,
        knowledge.suggest_answers,
        contexts=contexts,
        authorization=access,
        reference_grounding=ReferenceGrounding(
            knowledge.references,
            reference_proposer,
            Utf8BudgetCounter(),
            clock,
        ),
        references=knowledge.source_impact,
        reviews=knowledge.reference_currency,
    )
    return AnalysisWorkflowWiring(
        generation_context_tokens=contexts,
        requirement_commands=RequirementCommands(access, contexts),
        analysis_collaboration=collaboration,
        analyze_requirement=AnalyzeRequirement(collaboration),
        clarify_requirement_analysis=ClarifyRequirementAnalysis(collaboration),
        confirm_requirement_analysis=ConfirmRequirementAnalysis(
            persistence.requirement_repository,
            persistence.analysis_repository,
            clock,
            access,
            persistence.analysis_audit_repository,
            knowledge.review,
            persistence.transaction_manager,
            knowledge.source_impact,
        ),
        get_requirement_analysis=GetRequirementAnalysis(
            persistence.requirement_repository, persistence.analysis_repository
        ),
    )
