"""Domain errors raised by breakdown review behavior."""


class InvalidReviewContentError(Exception):
    """Review content violates a domain invariant."""


class FlagResolutionNotAllowedError(Exception):
    """A flag requires a source action rather than a decision."""


class FlagResolutionConflictError(Exception):
    """A flag was already resolved by a different decision."""


class InvalidReviewTransitionError(Exception):
    """The requested governance lifecycle transition is not allowed."""
