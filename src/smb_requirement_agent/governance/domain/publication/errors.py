"""Publication record invariants and refusals (Slice 13)."""


class InvalidPublicationError(Exception):
    """A publication record would break one of its invariants."""


class PublicationInProgressError(Exception):
    """Another publication of this Requirement is still running."""
