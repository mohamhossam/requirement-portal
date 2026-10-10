"""Outbound boundary for publishing an approved backlog to a work-item tracker (Slices 12-13)."""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.governance.application.publication import (
    PlannedWorkItem,
    PublicationTarget,
    PublishedWorkItem,
)


class BacklogPublisherPort(Protocol):
    def target(self) -> PublicationTarget:
        """Where items go. Raises `PublicationUnavailableError` when nothing is configured."""
        ...

    def create(self, item: PlannedWorkItem, parent: PublishedWorkItem | None) -> PublishedWorkItem:
        """Create one work item, tagged with the item's marker and linked under its parent.

        Raises `PublicationTargetError` when the tracker refuses the item or cannot be
        reached; nothing is retried here, because a lost answer may hide a created item.
        """
        ...

    def update(self, external_id: str, item: PlannedWorkItem) -> PublishedWorkItem:
        """Replace an existing item's title, description and acceptance criteria.

        Where the item sits and its state are left as people set them in the tracker.
        Raises `PublicationTargetError` like `create`.
        """
        ...

    def find(self, item: PlannedWorkItem) -> PublishedWorkItem | None:
        """The tracker item carrying this item's marker, if one exists.

        Raises `PublicationTargetError` when the tracker cannot answer, or when several
        items carry the marker and no one item can be trusted.
        """
        ...
