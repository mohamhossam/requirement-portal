"""Saved-view and reporting-window failures raised by the reporting use cases."""


class SavedViewNotFoundError(Exception):
    """A requested saved worklist view is absent or belongs to another actor."""


class SavedViewConflictError(Exception):
    """A saved-view name or optimistic version conflicts with current state."""


class InvalidSavedViewError(Exception):
    """Saved-view content violates the reusable-view contract."""


class InvalidReportingWindowError(Exception):
    """The requested operational reporting window is unsupported."""
