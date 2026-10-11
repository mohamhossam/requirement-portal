"""Persistence boundary for publication records (Slice 13)."""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.governance.domain.publication.entities import BacklogPublication
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class PublicationRepositoryPort(Protocol):
    def get(self, requirement_id: RequirementId) -> BacklogPublication | None: ...

    def find_by_work_item(self, kind: str, external_id: str) -> BacklogPublication | None:
        """The record holding the tracker item `external_id` of this kind, such as the Epic
        a tracker event names (ontology plan Phase 7)."""
        ...

    def save(self, publication: BacklogPublication) -> None:
        """Save a record one version on from the stored one, or the first record.

        Raises `ArtifactVersionConflictError` when another writer saved first.
        """
        ...
