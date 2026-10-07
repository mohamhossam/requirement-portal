"""Epic generator port.

A single-method port rather than a shared decomposition port: per AGENTS.md
section 16, the abstraction waits for evidence of a second use case. Whether
Slice 04's Feature generation shares enough to justify unification is a
decision for that slice.
"""

from __future__ import annotations

from typing import Protocol, TypedDict

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement


class EpicCandidate(TypedDict):
    """A provider-independent structured Epic proposal.

    `model` and `prompt_version` are reported by the adapter so the use case can
    stamp provenance without knowing which provider ran.
    """

    name: str
    outcome: str
    business_case: str
    model: str
    prompt_version: str


class EpicGeneratorPort(Protocol):
    """Outbound port for generating an Epic candidate from analysed input."""

    def generate(self, requirement: Requirement, analysis: RequirementAnalysis) -> EpicCandidate:
        """Generate an Epic candidate.

        Raises EpicGenerationError on failure or unusable output.
        """
        ...
