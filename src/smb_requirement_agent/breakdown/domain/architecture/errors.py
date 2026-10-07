"""Architecture impact domain errors."""


class ArchitectureError(Exception):
    """Base error for architecture impact behavior."""


class InvalidArchitectureContentError(ArchitectureError):
    """Raised when architecture knowledge or an impact violates its invariants."""
