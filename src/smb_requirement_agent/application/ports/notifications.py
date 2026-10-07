"""Actor notification persistence boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from smb_requirement_agent.domain.jobs.entities import (
    ActorNotification,
    NotificationId,
    NotificationPreference,
)
from smb_requirement_agent.domain.shared.actors import ActorId


class NotificationRepositoryPort(Protocol):
    def add(self, notification: ActorNotification) -> None: ...

    def get(self, notification_id: NotificationId) -> ActorNotification | None: ...

    def save(self, notification: ActorNotification) -> None: ...

    def list_for_actor(
        self, actor_id: ActorId, *, unread_only: bool = False, limit: int | None = None
    ) -> list[ActorNotification]:
        """Newest first; `limit` keeps only the newest rows, None keeps all."""
        ...

    def delete_read_before(self, cutoff: datetime) -> int:
        """Delete notifications read before `cutoff`; unread ones are kept."""
        ...

    def get_preference(self, actor_id: ActorId) -> NotificationPreference: ...

    def save_preference(self, preference: NotificationPreference) -> None: ...
