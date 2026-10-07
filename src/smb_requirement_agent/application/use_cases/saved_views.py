"""Actor-scoped reusable Requirement worklist view operations."""

from __future__ import annotations

import uuid
from dataclasses import replace

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    SavedViewConflictError,
    SavedViewNotFoundError,
)
from smb_requirement_agent.application.ports.saved_views import (
    SavedRequirementView,
    SavedViewCriteria,
    SavedViewRepositoryPort,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile


class SavedViews:
    def __init__(self, repository: SavedViewRepositoryPort, clock: ClockPort) -> None:
        self._repository = repository
        self._clock = clock

    def list(self, actor: ActorProfile) -> tuple[SavedRequirementView, ...]:
        return tuple(self._repository.list_for_actor(actor.id))

    def create(
        self, actor: ActorProfile, name: str, criteria: SavedViewCriteria
    ) -> SavedRequirementView:
        if self._repository.name_exists(actor.id, name):
            raise SavedViewConflictError("A saved view with this name already exists.")
        now = self._clock.now()
        view = SavedRequirementView(str(uuid.uuid4()), actor.id, name, criteria, 1, now, now)
        self._repository.add(view)
        return view

    def update(
        self,
        actor: ActorProfile,
        view_id: str,
        name: str,
        criteria: SavedViewCriteria,
        expected_version: int,
    ) -> SavedRequirementView:
        current = self._owned(view_id, actor)
        if current.version != expected_version:
            raise SavedViewConflictError("The saved view changed since it was loaded.")
        if self._repository.name_exists(actor.id, name, excluding_id=view_id):
            raise SavedViewConflictError("A saved view with this name already exists.")
        updated = replace(
            current,
            name=name,
            criteria=criteria,
            version=current.version + 1,
            updated_at=self._clock.now(),
        )
        self._repository.save(updated, expected_version)
        return updated

    def delete(self, actor: ActorProfile, view_id: str, expected_version: int) -> None:
        current = self._owned(view_id, actor)
        if current.version != expected_version:
            raise SavedViewConflictError("The saved view changed since it was loaded.")
        self._repository.delete(view_id, expected_version)

    def _owned(self, view_id: str, actor: ActorProfile) -> SavedRequirementView:
        view = self._repository.get(view_id)
        if view is None or view.actor_id != actor.id:
            raise SavedViewNotFoundError("Saved view not found.")
        return view
