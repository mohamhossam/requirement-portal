"""Published references, as analysis asks for and checks them.

Analysis-shaped half of the old `reference_grounding` ports: what analysis asks of a reference
proposer and how its analysis is augmented with the proposals (ADR-0103 PR 10), and whether the
references an analysis and its proposals cite are still current (PR 15a).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.analysis.application.errors import RequirementAnalysisConflictError
from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.analysis.domain.value_objects import (
    IntentProposal,
    IntentProposalKind,
)
from smb_requirement_agent.references.application.ports.reference_grounding import ReferenceEvidence
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.citation import PublishedReference


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


def require_analysis_references(
    port: ReferenceEvidencePort, analysis: RequirementAnalysis, *, target_ids: Sequence[str] = ()
) -> None:
    if port.stale_analysis(analysis, target_ids=target_ids):
        raise RequirementAnalysisConflictError(
            "Cited evidence changed. Review source impact before continuing."
        )
