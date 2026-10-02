"""Immutable published-reference evidence; applicability is a separate human decision."""

from dataclasses import dataclass

from smb_requirement_agent.domain.document.errors import InvalidDocumentError


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
