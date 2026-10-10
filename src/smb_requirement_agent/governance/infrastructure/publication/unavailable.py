"""The publisher of a deployment with no work-item tracker configured."""

from __future__ import annotations

from smb_requirement_agent.governance.application.errors import PublicationUnavailableError
from smb_requirement_agent.governance.application.publication import (
    PlannedWorkItem,
    PublicationTarget,
    PublishedWorkItem,
)

MESSAGE = "Publishing to Azure DevOps is not set up for this portal (ADO_PUBLISHER)."


class UnavailableBacklogPublisher:
    def target(self) -> PublicationTarget:
        raise PublicationUnavailableError(MESSAGE)

    def create(self, item: PlannedWorkItem, parent: PublishedWorkItem | None) -> PublishedWorkItem:
        raise PublicationUnavailableError(MESSAGE)
