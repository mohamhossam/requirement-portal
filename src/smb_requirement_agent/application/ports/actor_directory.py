"""Persistence boundary for provider-neutral actors seen by the workspace."""

from typing import Protocol

from smb_requirement_agent.domain.identity.entities import ActorId, ActorProfile


class ActorDirectoryPort(Protocol):
    def record(self, actor: ActorProfile) -> None: ...

    def get(self, actor_id: ActorId) -> ActorProfile | None: ...

    def search(self, query: str | None, limit: int) -> list[ActorProfile]: ...
