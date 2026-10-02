"""Provider-neutral identity boundary."""

from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.application.errors import AuthenticationRequiredError
from smb_requirement_agent.domain.identity.errors import AuthorizationDeniedError


@dataclass(frozen=True)
class Actor:
    id: str
    roles: frozenset[str]

    @property
    def may_maintain_knowledge(self) -> bool:
        return "knowledge_maintainer" in self.roles


class IdentityPort(Protocol):
    def authenticate(self, authorization: str | None) -> Actor: ...


AuthenticationError = AuthenticationRequiredError
AuthorizationError = AuthorizationDeniedError


def require_maintainer(actor: Actor) -> None:
    if not actor.may_maintain_knowledge:
        raise AuthorizationError("Architecture knowledge maintenance requires a maintainer role.")


def require_reader(actor: Actor) -> None:
    if not ({"knowledge_reader", "knowledge_maintainer"} & actor.roles):
        raise AuthorizationError("Architecture knowledge requires a reader role.")
