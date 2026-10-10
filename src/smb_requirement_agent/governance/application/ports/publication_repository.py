"""Persistence boundary for publication records (Slice 13)."""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.governance.domain.publication.entities import BacklogPublication
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class PublicationRepositoryPort(Protocol):
    def get(self, requirement_id: RequirementId) -> BacklogPublication | None: ...

    def save(self, publication: BacklogPublication) -> None:
        """Save a record one version on from the stored one, or the first record.

        Raises `ArtifactVersionConflictError` when another writer saved first.
        """
        ...
