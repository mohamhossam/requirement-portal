"""In-memory saved Requirement views for offline use and tests."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from smb_requirement_agent.application.errors import SavedViewConflictError
from smb_requirement_agent.application.ports.saved_views import SavedRequirementView
from smb_requirement_agent.domain.shared.actors import ActorId


class InMemorySavedViewRepository:
    """Views are saved outside any unit of work, so the store takes the shared graph lock.

    Otherwise a save from a request thread could land inside a transaction
    another thread owns, which would count it as its own write and roll it back.
    """

    def __init__(self, *, lock: RLock | None = None) -> None:
        self._views: dict[str, SavedRequirementView] = {}
        self._lock = lock or RLock()

    def snapshot_state(self) -> Any:
        return deepcopy((self._views,))

    def restore_state(self, state: Any) -> None:
        (self._views,) = deepcopy(state)

    def list_for_actor(self, actor_id: ActorId) -> list[SavedRequirementView]:
        with self._lock:
            views = tuple(self._views.values())
        return sorted(
            (item for item in views if item.actor_id == actor_id),
            key=lambda item: item.name.casefold(),
        )

    def get(self, view_id: str) -> SavedRequirementView | None:
        with self._lock:
            return self._views.get(view_id)

    def add(self, view: SavedRequirementView) -> None:
        with self._lock:
            if view.id in self._views:
                raise SavedViewConflictError("Saved view already exists.")
            self._views[view.id] = view

    def save(self, view: SavedRequirementView, expected_version: int) -> None:
        with self._lock:
            current = self._views.get(view.id)
            if current is None or current.version != expected_version:
                raise SavedViewConflictError("The saved view changed since it was loaded.")
            self._views[view.id] = view

    def delete(self, view_id: str, expected_version: int) -> None:
        with self._lock:
            current = self._views.get(view_id)
            if current is None or current.version != expected_version:
                raise SavedViewConflictError("The saved view changed since it was loaded.")
            del self._views[view_id]

    def name_exists(self, actor_id: ActorId, name: str, *, excluding_id: str | None = None) -> bool:
        normalized = name.strip().casefold()
        with self._lock:
            views = tuple(self._views.values())
        return any(
            item.actor_id == actor_id
            and item.id != excluding_id
            and item.name.casefold() == normalized
            for item in views
        )
