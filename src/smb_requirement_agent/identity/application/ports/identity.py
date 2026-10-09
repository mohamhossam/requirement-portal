"""Provider-neutral identity boundary."""

from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.application.errors import AuthenticationRequiredError
from smb_requirement_agent.identity.domain.errors import AuthorizationDeniedError

# The roles architecture mapping checks, owned by requirement work (ADR-0104).
# A maintainer is also a reader.
ARCHITECTURE_READER = "architecture_reader"
ARCHITECTURE_MAINTAINER = "architecture_maintainer"

MAINTAINER_ROLES = frozenset({ARCHITECTURE_MAINTAINER})
READER_ROLES = frozenset({ARCHITECTURE_READER}) | MAINTAINER_ROLES


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


def require_reader(actor: Actor) -> None:
    if not READER_ROLES & actor.roles:
        raise AuthorizationError("Architecture knowledge requires a reader role.")
