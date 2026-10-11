"""Evidence and corrective feedback supplied to backlog generators."""

from dataclasses import dataclass

from smb_requirement_agent.analysis.domain.product_impact import ProductImpact
from smb_requirement_agent.references.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
)


@dataclass(frozen=True)
class GenerationGuidance:
    architecture: ArchitectureKnowledgeMatch | None = None
    potential_dependencies: tuple[str, ...] = ()
    ambiguities: tuple[str, ...] = ()
    feedback: tuple[str, ...] = ()
    previous_draft: tuple[str, ...] = ()
    minimum_story_count: int = 1
    # The product impact a person accepted or overrode in analysis (ADR-0116). When set it
    # takes the place of a fresh architecture match; unknown or none adds nothing.
    product_impact: ProductImpact | None = None


EMPTY_GENERATION_GUIDANCE = GenerationGuidance()
