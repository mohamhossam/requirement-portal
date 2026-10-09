"""Provider-neutral identity boundary."""

from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.application.errors import AuthenticationRequiredError
from smb_requirement_agent.identity.domain.errors import AuthorizationDeniedError

# The role architecture mapping checks, owned by requirement work (ADR-0104). Starting and
# reading a mapping needs only membership of the Requirement (ADR-0104 amendment, 2026-10-09);
# a maintainer may also cancel and retry other people's mapping jobs.
ARCHITECTURE_MAINTAINER = "architecture_maintainer"

MAINTAINER_ROLES = frozenset({ARCHITECTURE_MAINTAINER})


@dataclass(frozen=True)
class Actor:
    id: str
    roles: frozenset[str]

    @property
    def may_maintain_knowledge(self) -> bool:
        return bool(MAINTAINER_ROLES & self.roles)


class IdentityPort(Protocol):
    def authenticate(self, authorization: str | None) -> Actor: ...


AuthenticationError = AuthenticationRequiredError
AuthorizationError = AuthorizationDeniedError


def require_maintainer(actor: Actor) -> None:
    if not actor.may_maintain_knowledge:
        raise AuthorizationError("Architecture knowledge maintenance requires a maintainer role.")
