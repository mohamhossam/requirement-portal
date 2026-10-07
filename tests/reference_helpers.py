"""Explicit empty-corpus fixture for tests unrelated to document references."""

from collections.abc import Sequence

from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.analysis.domain.value_objects import IntentProposal
from smb_requirement_agent.application.ports.reference_grounding import ReferenceEvidence
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.citation import PublishedReference


class EmptyReferences:
    def retrieve(self, query: str) -> tuple[ReferenceEvidence, ...]:
        return ()

    def augment(
        self,
        requirement: Requirement,
        primary: RequirementAnalysisCandidate,
        decisions: Sequence[IntentProposal],
    ) -> RequirementAnalysisCandidate:
        return primary

    def stale_analysis(
        self, analysis: RequirementAnalysis, *, target_ids: Sequence[str] | None = None
    ) -> tuple[str, ...]:
        return self.stale_proposals(analysis.intent_proposals)

    def stale_proposals(self, proposals: Sequence[IntentProposal]) -> tuple[str, ...]:
        return ()

    def require_current(self, evidence: Sequence[PublishedReference]) -> None:
        assert not evidence, "Use real reference validation when a test supplies citations."
