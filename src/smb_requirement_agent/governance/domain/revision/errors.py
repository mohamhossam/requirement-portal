"""Revision-domain errors."""


class RevisionNotFoundError(Exception):
    """Raised when a requested immutable revision does not exist."""


class InvalidRevisionError(Exception):
    """Raised when a revision number is invalid."""
