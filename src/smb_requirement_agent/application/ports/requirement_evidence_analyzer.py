"""Focused structured-evidence analysis and fragment-cache ports."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from smb_requirement_agent.application.ports.requirement_analyzer import (
    ActiveQuestionContext,
    AnalysisDocumentContext,
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.domain.analysis.value_objects import HumanClarification, IntentProposal
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.shared.identifiers import RequirementId


class RequirementEvidenceAnalyzerPort(Protocol):
    """Analyze one bounded evidence packet with provider-validated citations."""

    @property
    def model(self) -> str: ...

    @property
    def prompt_version(self) -> str: ...

    def analyze_evidence(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext],
        intent_decisions: Sequence[IntentProposal],
        active_questions: Sequence[ActiveQuestionContext],
    ) -> RequirementAnalysisCandidate: ...


@dataclass(frozen=True)
class EvidenceFragmentCacheEntry:
    candidate: RequirementAnalysisCandidate
    generated_at: datetime


class EvidenceFragmentCachePort(Protocol):
    def get(self, key: str) -> EvidenceFragmentCacheEntry | None: ...

    def put(self, key: str, value: EvidenceFragmentCacheEntry) -> None: ...

    def put_many(self, values: Sequence[tuple[str, EvidenceFragmentCacheEntry]]) -> None: ...


class AnalysisProgressPort(Protocol):
    def report(
        self,
        requirement_id: RequirementId,
        phase: str,
        completed_units: int,
        total_units: int,
        current_section_label: str | None,
    ) -> None: ...
