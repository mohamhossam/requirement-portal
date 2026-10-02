"""Epic domain errors."""


class EpicError(Exception):
    """Base error for all Epic domain errors."""


class InvalidEpicContentError(EpicError):
    """Raised when an Epic field is empty or otherwise invalid."""


class StaleEpicApprovalError(EpicError):
    """Raised when approval is attempted on an Epic whose source has changed."""


class EpicRegenerationConflictError(EpicError):
    """Raised when regeneration would discard human work without an explicit force."""


class EpicNotApprovedError(EpicError):
    """Raised when an Epic must be approved and current before it can be used."""
