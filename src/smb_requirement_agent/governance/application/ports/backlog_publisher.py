"""Outbound boundary for publishing an approved backlog to a work-item tracker (Slice 12)."""

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
        """Create one work item, linked under its parent when it has one.

        Raises `PublicationTargetError` when the tracker refuses the item or cannot be
        reached; nothing is retried here, because a lost answer may hide a created item.
        """
        ...
