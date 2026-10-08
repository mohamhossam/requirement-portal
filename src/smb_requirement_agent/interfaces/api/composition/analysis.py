"""Requirement analysis: the analyzer pipeline and the workflow around it.

The evidence-packet pipeline wraps the selected analyzer. The workflow covers generation,
clarification and confirmation, and owns the generation-context tokens every model-backed action
checks, so a person only acts on the context they were shown. ADR-0103 PR 10 merged the two
builders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.ports.reference_analysis import (
    ReferenceProposerPort,
)
from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    RequirementAnalyzerPort,
)
from smb_requirement_agent.analysis.application.ports.requirement_evidence_analyzer import (
    RequirementEvidenceAnalyzerPort,
)
from smb_requirement_agent.analysis.application.use_cases.analysis_collaboration import (
    AnalysisCollaboration,
)
from smb_requirement_agent.analysis.application.use_cases.analysis_documents import (
    AssembleAnalysisDocuments,
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
from smb_requirement_agent.analysis.application.use_cases.evidence_analysis import (
    AnalyzeEvidencePacket,
    AssembleRequirementEvidence,
    ConsolidateEvidenceAnalysis,
    PlanEvidencePackets,
    StructuredRequirementAnalyzer,
    ValidateAnalysisCitations,
)
from smb_requirement_agent.analysis.application.use_cases.get_requirement_analysis import (
    GetRequirementAnalysis,
)
from smb_requirement_agent.analysis.application.use_cases.reference_grounding import (
    ReferenceGrounding,
)
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.text.budget import Utf8BudgetCounter
from smb_requirement_agent.interfaces.api.composition.knowledge import RequirementKnowledgeWiring
from smb_requirement_agent.interfaces.api.composition.llm import LLMAdapters
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters
from smb_requirement_agent.workflows.application.use_cases.ai_jobs import AnalysisProgressReporter
from smb_requirement_agent.workflows.application.use_cases.generation_context import (
    GenerationContextTokens,
)
from smb_requirement_agent.workflows.application.use_cases.identity_access import (
    RequirementAccessService,
)
from smb_requirement_agent.workflows.application.use_cases.requirement_commands import (
    RequirementCommands,
)

# A provider without a configured context window gets this evidence budget.
_DEFAULT_EVIDENCE_CHARACTERS = 60_000
# Rough characters per token used to turn a token window into an evidence budget.
_CHARACTERS_PER_TOKEN = 4


def build_requirement_analyzer(
    settings: Settings,
    llm: LLMAdapters,
    persistence: PersistenceAdapters,
    clock: ClockPort,
) -> RequirementAnalyzerPort:
    """Wrap the provider analyzer in evidence packing, citation checks and progress."""
    evidence_analyzer = cast(RequirementEvidenceAnalyzerPort, llm.analyzer)
    citation_validator = ValidateAnalysisCitations()
    packet_planner = PlanEvidencePackets(_evidence_budget(settings))
    packet_analyzer = AnalyzeEvidencePacket(
        evidence_analyzer,
        citation_validator,
        persistence.evidence_fragment_cache,
        clock,
    )
    return StructuredRequirementAnalyzer(
        llm.analyzer,
        AssembleRequirementEvidence(),
        packet_planner,
        packet_analyzer,
        ConsolidateEvidenceAnalysis(packet_planner, packet_analyzer),
        citation_validator,
        clock,
        AnalysisProgressReporter(persistence.ai_job_repository, clock),
    )


def _evidence_budget(settings: Settings) -> int:
    available_characters = _DEFAULT_EVIDENCE_CHARACTERS
    if settings.llm_provider is LLMProvider.LOCAL:
        available_characters = (
            settings.local_llm_context_window_tokens - settings.local_llm_max_output_tokens
        ) * _CHARACTERS_PER_TOKEN
    if settings.llm_profiles:
        analysis_profile = settings.llm_profiles.for_task("analysis")
        available_characters = min(
            available_characters,
            (analysis_profile.context_tokens - analysis_profile.output_tokens)
            * _CHARACTERS_PER_TOKEN,
        )
    return available_characters


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
