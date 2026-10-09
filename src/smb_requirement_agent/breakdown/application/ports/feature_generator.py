"""Feature generator port.

Separate from EpicGeneratorPort rather than sharing a BacklogDecompositionPort:
the two differ in inputs and cardinality and share no behaviour, so combining
them would group unrelated methods rather than abstract anything. See
docs/architecture/adr-0005-separate-generator-ports.md.
"""

from __future__ import annotations

from typing import Protocol, TypedDict

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.breakdown.application.ports.generation_guidance import (
    EMPTY_GENERATION_GUIDANCE,
    GenerationGuidance,
)
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement


class FeatureCandidate(TypedDict):
    """A provider-independent structured Feature proposal.

    `delivery_drop` and `splitting_pattern` are plain strings here; mapping them
    onto the domain enums is the use case's job, and an unrecognised value is a
    generation failure rather than a silent default.
    """

    name: str
    outcome: str
    delivery_drop: str
    splitting_pattern: str
    splitting_rationale: str
    model: str
    prompt_version: str


class FeatureGeneratorPort(Protocol):
    """Outbound port for decomposing an approved Epic into Feature candidates."""

    def generate(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        *,
        guidance: GenerationGuidance = EMPTY_GENERATION_GUIDANCE,
    ) -> list[FeatureCandidate]:
        """Generate Feature candidates.

        Raises FeatureGenerationError on failure or unusable output, including
        a response containing no Features at all.
        """
        ...
