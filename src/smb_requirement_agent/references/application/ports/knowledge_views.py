"""What requirement work's read-only viewers show from the knowledge service (ADR-0099).

Any member of a citing Requirement may open the exact library passage it
cites, or the evidence behind an architecture impact. The knowledge service
serves only live publications and published releases; anything else is absent.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class PassageCitation:
    document_id: str
    publication_id: str
    version_id: str
    revision_id: str
    block_id: str


@dataclass(frozen=True)
class CitedPassage:
    document_id: str
    title: str
    publication_id: str
    version_id: str
    version_number: int
    revision_id: str
    block_id: str
    section_path: tuple[str, ...]
    label: str
    text: str
    # When its document falls due for review again (Knowledge Center D).
    review_due_on: date | None = None


@dataclass(frozen=True)
class ArchitectureEvidence:
    id: str
    source_label: str
    location: str
    text: str
    document_version_id: str | None = None
    # For a catalogue system's own record: when that system falls due for review again.
    system_review_due_on: date | None = None


class KnowledgeViewsPort(Protocol):
    def passage(self, citation: PassageCitation) -> CitedPassage | None:
        """The cited passage while its publication is live; otherwise nothing."""
        ...

    def evidence(self, release_id: str, chunk_id: str) -> ArchitectureEvidence | None:
        """Evidence of a published release; otherwise nothing."""
        ...
