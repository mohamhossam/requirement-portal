"""Port for placing an analysed requirement in the product portfolio (ADR-0115)."""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.analysis.domain.value_objects import HumanClarification
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement


class ProductImpactPort(Protocol):
    def augment(
        self,
        requirement: Requirement,
        candidate: RequirementAnalysisCandidate,
        clarifications: tuple[HumanClarification, ...],
    ) -> RequirementAnalysisCandidate:
        """Add the round's product impact and its status to the analysed facts.

        Never fails the analysis: an unreachable knowledge portal is recorded as
        `unavailable`, and none linked as `not_connected`.
        """
        ...
