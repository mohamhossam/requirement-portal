"""Requirement analysis: the evidence-packet pipeline around the selected analyzer."""

from __future__ import annotations

from typing import cast

from smb_requirement_agent.application.ports.clock import ClockPort
from smb_requirement_agent.application.ports.requirement_analyzer import RequirementAnalyzerPort
from smb_requirement_agent.application.ports.requirement_evidence_analyzer import (
    RequirementEvidenceAnalyzerPort,
)
from smb_requirement_agent.application.use_cases.ai_jobs import AnalysisProgressReporter
from smb_requirement_agent.application.use_cases.evidence_analysis import (
    AnalyzeEvidencePacket,
    AssembleRequirementEvidence,
    ConsolidateEvidenceAnalysis,
    PlanEvidencePackets,
    StructuredRequirementAnalyzer,
    ValidateAnalysisCitations,
)
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.composition.llm import LLMAdapters
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters

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
