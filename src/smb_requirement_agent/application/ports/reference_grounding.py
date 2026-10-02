"""Focused applicability proposals and current-publication validation boundaries."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.application.errors import RequirementAnalysisConflictError
from smb_requirement_agent.application.ports.requirement_analyzer import (
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.analysis.value_objects import (
    IntentProposal,
    IntentProposalKind,
)
from smb_requirement_agent.domain.document.reference import PublishedReference
from smb_requirement_agent.domain.requirement.entities import Requirement


@dataclass(frozen=True)
class ReferenceEvidence:
    """Exact citable passage plus bounded, non-authoritative retrieval context."""

    citation: PublishedReference
    context_text: str
    context_locations: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceProposalCandidate:
    kind: IntentProposalKind
    statement: str
    rationale: str
    evidence: tuple[PublishedReference, ...]
    conflict: bool


@dataclass(frozen=True)
class ReferenceProposalResult:
    proposals: tuple[ReferenceProposalCandidate, ...]
    model: str
    prompt_version: str


class ReferenceProposerPort(Protocol):
    def propose(
        self,
        requirement: Requirement,
        primary: RequirementAnalysisCandidate,
        evidence: tuple[ReferenceEvidence, ...],
        decisions: Sequence[IntentProposal],
    ) -> ReferenceProposalResult: ...


class ReferenceAnalysisPort(Protocol):
    def augment(
        self,
        requirement: Requirement,
        primary: RequirementAnalysisCandidate,
        decisions: Sequence[IntentProposal],
    ) -> RequirementAnalysisCandidate: ...


class ReferenceEvidencePort(Protocol):
    def stale_analysis(
        self, analysis: RequirementAnalysis, *, target_ids: Sequence[str] | None = None
    ) -> tuple[str, ...]: ...
    def stale_proposals(self, proposals: Sequence[IntentProposal]) -> tuple[str, ...]: ...
    def require_current(self, evidence: Sequence[PublishedReference]) -> None: ...


class ReferenceSearchPort(ReferenceEvidencePort, Protocol):
    def retrieve(self, query: str) -> tuple[ReferenceEvidence, ...]: ...


class ReferenceKnowledgePort(Protocol):
    """What requirement work reads from the shared reference library (ADR-0099).

    Everything crosses as this application's own values (`ReferenceEvidence`,
    `PublishedReference`), never the library's chunks, so the library can move to
    its own service behind an HTTP adapter. Whether a citation is still current
    is answered locally, by `ReferenceEvidencePort`.
    """

    def retrieve(self, query: str) -> tuple[ReferenceEvidence, ...]: ...

    def has_published(self) -> bool: ...

    def search_evidence(self, query: str) -> tuple[ReferenceEvidence, ...]:
        """Every ranked hit for `query`, unbudgeted, each with its citation and context."""
        ...


def require_analysis_references(
    port: ReferenceEvidencePort, analysis: RequirementAnalysis, *, target_ids: Sequence[str] = ()
) -> None:
    if port.stale_analysis(analysis, target_ids=target_ids):
        raise RequirementAnalysisConflictError(
            "Cited evidence changed. Review source impact before continuing."
        )
