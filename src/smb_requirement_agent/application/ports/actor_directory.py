"""Persistence boundary for provider-neutral actors seen by the workspace."""

from typing import Protocol

from smb_requirement_agent.domain.shared.actors import (
    ActorId,
    ActorProfile,
)


class ActorLookupPort(Protocol):
    """Who an actor is, by id: all the knowledge service needs (ADR-0099)."""

    def get(self, actor_id: ActorId) -> ActorProfile | None: ...


class ActorDirectoryPort(ActorLookupPort, Protocol):
    def record(self, actor: ActorProfile) -> None: ...

    def search(self, query: str | None, limit: int) -> list[ActorProfile]: ...
