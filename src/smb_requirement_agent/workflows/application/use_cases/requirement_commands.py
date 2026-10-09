"""The one place a Requirement-scoped command's unit of work is assembled.

Every guarded HTTP action on a Requirement needs the same steps in the same
order: lock a consistent snapshot, authorize the actor, run the use case
(which may suspend the transaction around I/O), reauthorize before its writes
commit, and build the result view from that same snapshot. Assembling those
steps per route let each route order them slightly differently; delivery code
now names the command and how to present it, and this service does the rest.
"""

from __future__ import annotations

from collections.abc import Callable

from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementPermission,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.workflows.application.use_cases.generation_context import (
    GenerationContextTokens,
)
from smb_requirement_agent.workflows.application.use_cases.identity_access import (
    RequirementAccessService,
)


class RequirementCommands:
    def __init__(self, access: RequirementAccessService, contexts: GenerationContextTokens) -> None:
        self._access = access
        self._contexts = contexts

    def run[T](
        self,
        requirement_id: RequirementId,
        actor: ActorProfile,
        command: Callable[[], T],
    ) -> T:
        """Check membership, then run the command, fenced on both sides of any
        provider I/O it performs. (Model-backed work runs as a job, which checks
        the caller's generation context when it starts, ADR-0105.)

        Membership is the baseline every Requirement-scoped command needs. A
        command that needs more (the owner) states it in its own use case,
        through the same access service, so delivery code never chooses a
        permission.
        """
        with self._access.mutation(requirement_id, actor, RequirementPermission.MEMBER):
            return command()

    def run_and_present[T, R](
        self,
        requirement_id: RequirementId,
        actor: ActorProfile,
        command: Callable[[], T],
        present: Callable[[T], R],
    ) -> R:
        """As `run`, then build the view inside the same locked snapshot, so the
        context tokens it carries describe exactly the state the command left."""
        with self._contexts.read_snapshot(requirement_id):
            return present(self.run(requirement_id, actor, command))

    def read[R](self, requirement_id: RequirementId, read: Callable[[], R]) -> R:
        """Read a view and its context tokens from one consistent snapshot."""
        with self._contexts.read_snapshot(requirement_id):
            return read()
