"""Persistence boundary for the shared sample requirement list."""

from typing import Protocol

from smb_requirement_agent.domain.architecture.samples import SampleRequirementSet


class SampleRequirementsPort(Protocol):
    def load(self) -> SampleRequirementSet: ...

    def save(self, updated: SampleRequirementSet, expected_revision: int) -> None:
        """Store ``updated`` if the stored list is still at ``expected_revision``.

        Raises ``KnowledgeConflictError`` when another maintainer saved first.
        """
        ...
