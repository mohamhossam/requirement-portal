"""What a catalogue release change means for the backlog, in counts.

Maintainers publish catalogue versions but are not members of every
requirement, so they see how much is mapped and how much uses an older
version — never which requirements. Each requirement's own team remaps.
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.application.ports.architecture_knowledge_repository import (
    ArchitectureKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.architecture_mapping_stats import (
    ArchitectureMappingStatsPort,
)
from smb_requirement_agent.application.ports.identity import Actor, require_maintainer


@dataclass(frozen=True)
class MappingImpact:
    active_release_id: str
    requirements: int
    features: int
    stories: int
    outdated_requirements: int
    outdated_features: int
    outdated_stories: int


class ReportMappingImpact:
    def __init__(
        self,
        repository: ArchitectureKnowledgeRepositoryPort,
        stats: ArchitectureMappingStatsPort,
    ) -> None:
        self._repository = repository
        self._stats = stats

    def execute(self, actor: Actor) -> MappingImpact:
        require_maintainer(actor)
        active = self._repository.active().id
        counts = self._stats.by_release()
        outdated = [item for item in counts if item.release_id != active]
        # A requirement is pinned to one release per mapping, so its counts do not overlap.
        return MappingImpact(
            active,
            sum(item.requirements for item in counts),
            sum(item.features for item in counts),
            sum(item.stories for item in counts),
            sum(item.requirements for item in outdated),
            sum(item.features for item in outdated),
            sum(item.stories for item in outdated),
        )
