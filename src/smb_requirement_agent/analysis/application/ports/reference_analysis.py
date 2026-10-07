"""Focused applicability proposals from published references, as analysis asks for them.

Analysis-shaped half of the old `reference_grounding` ports (ADR-0103 PR 10): what analysis
asks of a reference proposer, and how its analysis is augmented with the proposals.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.analysis.domain.value_objects import (
    IntentProposal,
    IntentProposalKind,
)
from smb_requirement_agent.application.ports.reference_grounding import ReferenceEvidence
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
