"""Errors for shared domain concepts."""


class InvalidGeneratedContentError(Exception):
    """Raised when data shared by every generated aggregate is invalid.

    Covers provenance and staleness fields, which are constructed from the
    clock and the adapter rather than from client input. Reaching this is a
    programming error, not something a caller can provoke.
    """


class InvalidApprovalContentError(ValueError):
    """An approval, rejection, or review comment violates its invariants."""


class InvalidRequirementIdError(Exception):
    """A Requirement id is blank.

    Reported to clients exactly as the `InvalidRequirementContextError` it replaced for ids:
    code `invalid_requirement_context`, invalid input. Like that error it is not a `ValueError`,
    so no `except ValueError` starts catching blank ids.
    """
