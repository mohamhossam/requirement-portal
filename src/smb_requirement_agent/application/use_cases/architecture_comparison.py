"""Check a draft catalogue against the team's sample requirements before publishing.

Each sample is mapped twice: by the version in use and by the draft. The page
asks for one sample at a time, so a slow local model fills the table row by row
instead of holding one long request open.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgePort,
    ArchitectureQuery,
)
from smb_requirement_agent.application.ports.clock import ClockPort
from smb_requirement_agent.application.ports.identity import Actor, require_maintainer
from smb_requirement_agent.application.ports.sample_requirements import SampleRequirementsPort
from smb_requirement_agent.application.use_cases.architecture_knowledge import (
    ManageArchitectureKnowledge,
)
from smb_requirement_agent.application.use_cases.architecture_preview import (
    PreviewArchitectureImpact,
)
from smb_requirement_agent.domain.architecture.knowledge import InvalidKnowledgeError
from smb_requirement_agent.domain.architecture.samples import (
    SampleRequirement,
    SampleRequirementSet,
)


@dataclass(frozen=True)
class ComparedImpact:
    release_id: str
    systems: tuple[tuple[str, str], ...]
    uncertainty: str | None


@dataclass(frozen=True)
class ImpactComparison:
    query: str
    in_use: ComparedImpact
    this_version: ComparedImpact


class ManageSampleRequirements:
    def __init__(self, repository: SampleRequirementsPort, clock: ClockPort) -> None:
        self._repository = repository
        self._clock = clock

    def view(self, actor: Actor) -> SampleRequirementSet:
        require_maintainer(actor)
        return self._repository.load()

    def replace(
        self,
        items: tuple[tuple[str | None, str], ...],
        expected_revision: int,
        actor: Actor,
    ) -> SampleRequirementSet:
        """Replace the whole list; items without an id are new and get one."""
        require_maintainer(actor)
        samples = tuple(SampleRequirement(item_id or uuid4().hex, text) for item_id, text in items)
        updated = self._repository.load().replaced(samples, actor.id, self._clock.now())
        self._repository.save(updated, expected_revision)
        return updated


class CompareArchitectureImpact:
    def __init__(
        self,
        manage: ManageArchitectureKnowledge,
        preview: PreviewArchitectureImpact,
        knowledge: ArchitectureKnowledgePort,
    ) -> None:
        self._manage = manage
        self._preview = preview
        self._knowledge = knowledge

    def execute(self, release_id: str, query: str, actor: Actor) -> ImpactComparison:
        """Map `query` with the release in use and with `release_id`, which must be built."""
        require_maintainer(actor)
        if not query.strip():
            raise InvalidKnowledgeError("Retrieval query must not be blank.")
        draft = self._preview.execute(release_id, query, actor)
        names = {system.id: system.name for system in self._manage.get(release_id).systems}
        active = self._manage.active()
        in_use = self._knowledge.match(ArchitectureQuery((query,), release_id=active.id))
        return ImpactComparison(
            query,
            ComparedImpact(
                active.id,
                tuple((item.id, item.name) for item in in_use.systems if item.catalogued),
                in_use.uncertainty,
            ),
            ComparedImpact(
                release_id,
                tuple(
                    (system_id, names.get(system_id, system_id)) for system_id in draft.system_ids
                ),
                draft.uncertainty,
            ),
        )
