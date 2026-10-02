"""Document domain errors."""


class DocumentError(Exception):
    """Base error for source-document behavior."""


class InvalidDocumentError(DocumentError):
    """Document metadata or lifecycle state is invalid."""


class DocumentInclusionError(DocumentError):
    """A failed or removed version was selected for analysis."""
