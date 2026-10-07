"""Feature domain errors."""


class FeatureError(Exception):
    """Base error for all Feature domain errors."""


class InvalidFeatureContentError(FeatureError):
    """Raised when a Feature field is empty or otherwise invalid."""


class StaleFeatureApprovalError(FeatureError):
    """Raised when approval is attempted on a Feature whose source has changed."""


class FeatureRegenerationConflictError(FeatureError):
    """Raised when regeneration would discard human work without an explicit force."""
