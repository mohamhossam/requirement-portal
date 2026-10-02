"""In-memory actor directory and access repositories."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from smb_requirement_agent.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.application.ports.actor_directory import ActorDirectoryPort
from smb_requirement_agent.domain.identity.entities import (
    ActorId,
    ActorProfile,
    DraftOwnership,
    RequirementAccess,
)
from smb_requirement_agent.domain.identity.errors import RequirementAccessConflictError
from smb_requirement_agent.domain.requirement.value_objects import RequirementId


class InMemoryActorDirectory(ActorDirectoryPort):
    """Actors seen at sign-in.

    Every request records its actor outside any unit of work, so the directory
    takes the shared graph lock itself. A write from another thread must never
    land inside a transaction that thread does not own: the transaction would
    count it as its own write, refuse provider calls, and roll it back.
    """

    def __init__(self, actors: tuple[ActorProfile, ...] = (), *, lock: RLock | None = None) -> None:
        self._actors = {actor.id: actor for actor in actors}
        self._lock = lock or RLock()

    def snapshot_state(self) -> Any:
        return deepcopy((self._actors,))

    def restore_state(self, state: Any) -> None:
        (self._actors,) = deepcopy(state)

    def record(self, actor: ActorProfile) -> None:
        with self._lock:
            self._actors[actor.id] = actor

    def get(self, actor_id: ActorId) -> ActorProfile | None:
        with self._lock:
            return self._actors.get(actor_id)

    def search(self, query: str | None, limit: int) -> list[ActorProfile]:
        needle = (query or "").strip().casefold()
        with self._lock:
            actors = tuple(self._actors.values())
        matches = [
            actor
            for actor in actors
            if not needle
            or needle in actor.display_name.casefold()
            or (actor.email is not None and needle in actor.email.casefold())
        ]
        return sorted(matches, key=lambda actor: actor.display_name.casefold())[:limit]


class InMemoryAccessRepository(AccessRepositoryPort):
    def __init__(self) -> None:
        self._requirements: dict[RequirementId, RequirementAccess] = {}
        self._drafts: dict[RequirementId, DraftOwnership] = {}

    def snapshot_state(self) -> Any:
        return deepcopy(
            (
                self._requirements,
                self._drafts,
            )
        )

    def restore_state(self, state: Any) -> None:
        (
            self._requirements,
            self._drafts,
        ) = deepcopy(state)

    def get_requirement(self, requirement_id: RequirementId) -> RequirementAccess | None:
        return self._requirements.get(requirement_id)

    def save_requirement(self, access: RequirementAccess) -> None:
        existing = self._requirements.get(access.requirement_id)
        if existing is not None and (
            access.version != existing.version + 1
            or access.changes[: len(existing.changes)] != existing.changes
        ):
            raise RequirementAccessConflictError(
                "Requirement access changed while this operation was in progress."
            )
        self._requirements[access.requirement_id] = access

    def get_draft_ownership(self, draft_id: RequirementId) -> DraftOwnership | None:
        return self._drafts.get(draft_id)

    def save_draft_ownership(self, ownership: DraftOwnership) -> None:
        existing = self._drafts.get(ownership.draft_id)
        if (
            existing is not None
            and existing.owner is not None
            and ownership.owner != existing.owner
        ):
            raise RequirementAccessConflictError(
                "Draft ownership changed while this operation was in progress."
            )
        self._drafts[ownership.draft_id] = ownership

    def delete_draft_ownership(self, draft_id: RequirementId) -> None:
        self._drafts.pop(draft_id, None)
