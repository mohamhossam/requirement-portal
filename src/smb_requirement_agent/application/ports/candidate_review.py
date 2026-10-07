"""Governance's view of backlog candidates, as the breakdown asks for it (ADR-0103).

The breakdown sits upstream of governance, so generation reaches the review rules through this
port it owns. The composition root implements it with governance's review policy and refresh.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True)
class CandidateCritique:
    """What the review rules make of unsaved Feature candidates."""

    # True when the rules raise any flag. Generation retries on flags alone.
    has_flags: bool
    # The flags' details, then the recommendations' rationales, as generation feedback.
    feedback: tuple[str, ...]


class CandidateReviewPort(Protocol):
    def critique_features(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        features: tuple[Feature, ...],
    ) -> CandidateCritique:
        """Apply the breakdown review rules to Feature candidates that are not yet saved."""
        ...

    def refresh(self, requirement_id: RequirementId) -> None:
        """Rebuild the saved breakdown review, inside the caller's unit of work."""
        ...
