"""Immutable published-reference evidence; applicability is a separate human decision.

`PublishedReference` and `normalize_search`, the citation contract, live in the shared kernel
(`domain/shared/citation.py`). The payload codec for `ReferenceDocumentState` is infrastructure
(`infrastructure/persistence/knowledge_payloads.py`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

from smb_requirement_agent.domain.shared.citation import PublishedReference, normalize_search


@dataclass(frozen=True)
class CurrentPublication:
    """What a document's live publication lets a citation prove (ADR-0099)."""

    publication_id: str
    fingerprint: str
    version_id: str
    version_number: int
    revision_id: str
    # (block id, label) for every block of the published version.
    block_labels: tuple[tuple[str, str], ...]
    # (block id, text) for every passage the published revision includes.
    passages: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ReferenceDocumentState:
    """A library document's citable state, as the reference library publishes it.

    Requirement work keeps a local copy of these, fed by the library's events, so
    it can check citations without reading the library (ADR-0099). `version`
    advances on every change to the document.
    """

    document_id: str
    owner_id: str
    title: str
    version: int
    published: CurrentPublication | None = None
    # When the library says it falls due for review again (Knowledge Center D). A citation
    # of it reads "not reviewed since" once that day has passed; it is never withheld.
    review_due_on: date | None = None

    def review_overdue(self, today: date) -> bool:
        return self.review_due_on is not None and today >= self.review_due_on

    @property
    def publication_state(self) -> str:
        """How source-impact decisions identify the publication they were made against."""
        return f"{self.version}:{self.published.publication_id if self.published else 'withdrawn'}"

    def cites(self, citation: PublishedReference) -> bool:
        """True while `citation` still quotes this document's live publication exactly."""
        published = self.published
        if (
            published is None
            or published.publication_id != citation.publication_id
            or published.fingerprint != citation.approval_fingerprint
            or published.version_id != citation.version_id
            or published.revision_id != citation.revision_id
        ):
            return False
        passage = next(
            (text for block, text in published.passages if block == citation.block_id), None
        )
        return (
            passage is not None
            and self.title == citation.title
            and published.version_number == citation.version_number
            and any(
                block == citation.block_id and label == citation.location
                for block, label in published.block_labels
            )
            and hashlib.sha256(normalize_search(citation.excerpt).encode()).hexdigest()
            == citation.lineage_hash
            and passage[citation.start_offset : citation.end_offset] == citation.excerpt
        )
