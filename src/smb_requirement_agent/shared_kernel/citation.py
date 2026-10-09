"""The citation contract every context shares (ADR-0099, ADR-0103 Amendment 1).

A `PublishedReference` quotes one passage of a reviewed library publication exactly. Analysis,
screening and the backlog carry it through `SourceLineage`, and knowledge-portal publishes it,
so it lives in the shared kernel rather than in either side of that boundary.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from smb_kernel.documents.model import InvalidDocumentError


def normalize_search(text: str) -> str:
    """The normal form a citation's `lineage_hash` and reference search are computed over.

    It is part of the citation contract both contexts share (ADR-0099).
    """
    # Preserve original citation text. Search normalization removes Arabic tatweel/diacritics.
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFKC", text).casefold()
            if c != "ـ" and not ("ً" <= c <= "ٟ") and c != "ٰ"
        ).split()
    )


@dataclass(frozen=True)
class PublishedReference:
    document_id: str
    title: str
    version_id: str
    version_number: int
    revision_id: str
    publication_id: str
    approval_fingerprint: str
    block_id: str
    location: str
    excerpt: str
    start_offset: int
    end_offset: int
    lineage_hash: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.document_id,
                self.title,
                self.version_id,
                self.revision_id,
                self.publication_id,
                self.block_id,
                self.location,
                self.excerpt,
            )
        ):
            raise InvalidDocumentError(
                "Published reference identity, text and location are required."
            )
        if self.version_number < 1 or self.start_offset < 0 or self.end_offset <= self.start_offset:
            raise InvalidDocumentError("Published reference version or passage range is invalid.")
        if self.end_offset - self.start_offset != len(self.excerpt):
            raise InvalidDocumentError("Published reference range must identify its exact excerpt.")
        for value in (self.approval_fingerprint, self.lineage_hash):
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise InvalidDocumentError("Published reference requires SHA-256 provenance.")
