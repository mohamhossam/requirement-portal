"""An offline publisher that keeps what it is sent (ADO_PUBLISHER=fake, AGENTS.md §4.5).

It lets the portal run publication end to end with no tracker account. Its links point
at a reserved domain that never resolves.
"""

from __future__ import annotations

from threading import Lock

from smb_requirement_agent.governance.application.publication import (
    PlannedWorkItem,
    PublicationTarget,
    PublishedWorkItem,
)


class FakeBacklogPublisher:
    def __init__(self) -> None:
        self._lock = Lock()
        self._created: list[tuple[PlannedWorkItem, PublishedWorkItem, str | None]] = []
        self._updated: list[tuple[str, PlannedWorkItem]] = []

    def target(self) -> PublicationTarget:
        return PublicationTarget(
            key="fake:local",
            system="Offline stand-in",
            project="Local",
            default_location="Local",
            details=(("Mode", "Nothing leaves this portal; items are kept in memory."),),
        )

    def create(self, item: PlannedWorkItem, parent: PublishedWorkItem | None) -> PublishedWorkItem:
        with self._lock:
            number = len(self._created) + 1
            created = PublishedWorkItem(
                key=item.key,
                external_id=str(number),
                url=f"https://work-items.example.invalid/{number}",
            )
            self._created.append((item, created, parent.external_id if parent else None))
            return created

    def update(self, external_id: str, item: PlannedWorkItem) -> PublishedWorkItem:
        with self._lock:
            self._updated.append((external_id, item))
            return PublishedWorkItem(
                item.key, external_id, f"https://work-items.example.invalid/{external_id}"
            )

    def find(self, item: PlannedWorkItem) -> PublishedWorkItem | None:
        with self._lock:
            return next(
                (created for sent, created, _ in self._created if sent.marker == item.marker),
                None,
            )

    @property
    def updated(self) -> tuple[tuple[str, PlannedWorkItem], ...]:
        """Each update sent, by the tracker id it went to."""
        with self._lock:
            return tuple(self._updated)

    @property
    def created(self) -> tuple[tuple[PlannedWorkItem, PublishedWorkItem, str | None], ...]:
        """Each item sent, what it became, and its parent's id."""
        with self._lock:
            return tuple(self._created)
