"""Evidence and corrective feedback supplied to backlog generators."""

from dataclasses import dataclass

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


EMPTY_GENERATION_GUIDANCE = GenerationGuidance()
