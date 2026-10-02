"""The one place a Requirement-scoped command's unit of work is assembled.

Every guarded HTTP action on a Requirement needs the same steps in the same
order: lock a consistent snapshot, authorize the actor, confirm the generation
context the caller last saw is still current, run the use case (which may
suspend the transaction around provider I/O), reauthorize before its writes
commit, and build the result view from that same snapshot. Assembling those
steps per route let each route order them slightly differently; delivery code
now names the command and how to present it, and this service does the rest.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementAccessService,
    RequirementPermission,
)
from smb_requirement_agent.domain.identity.entities import ActorProfile
from smb_requirement_agent.domain.requirement.value_objects import RequirementId


@dataclass(frozen=True)
class ExpectedContext:
    """The generation context token a caller displayed, and how to compute it now."""

    token: str
    current: Callable[[], str]


class RequirementCommands:
    def __init__(self, access: RequirementAccessService, contexts: GenerationContextTokens) -> None:
        self._access = access
        self._contexts = contexts

    def run[T](
        self,
        requirement_id: RequirementId,
        actor: ActorProfile,
        command: Callable[[], T],
        *,
        expected: ExpectedContext | None = None,
    ) -> T:
        """Check membership and the caller's context, then run the command, fenced
        on both sides of any provider I/O it performs.

        Membership is the baseline every Requirement-scoped command needs. A
        command that needs more (the owner) states it in its own use case,
        through the same access service, so delivery code never chooses a
        permission.
        """
        with self._access.mutation(requirement_id, actor, RequirementPermission.MEMBER):
            if expected is not None:
                self._contexts.require(expected.token, expected.current())
            return command()

    def run_and_present[T, R](
        self,
        requirement_id: RequirementId,
        actor: ActorProfile,
        command: Callable[[], T],
        present: Callable[[T], R],
        *,
        expected: ExpectedContext | None = None,
    ) -> R:
        """As `run`, then build the view inside the same locked snapshot, so the
        context tokens it carries describe exactly the state the command left."""
        with self._contexts.read_snapshot(requirement_id):
            return present(self.run(requirement_id, actor, command, expected=expected))

    def read[R](self, requirement_id: RequirementId, read: Callable[[], R]) -> R:
        """Read a view and its context tokens from one consistent snapshot."""
        with self._contexts.read_snapshot(requirement_id):
            return read()
