"""Domain errors for the Requirement aggregate."""


class RequirementError(Exception):
    """Base error for all Requirement domain errors."""


class InvalidRequirementTitleError(RequirementError):
    """Raised when a requirement title fails domain validation."""


class InvalidRequirementDescriptionError(RequirementError):
    """Raised when a requirement description fails domain validation."""


class InvalidRequirementContextError(RequirementError):
    """Raised when a supplied structured context value is blank."""


class RequirementIntakeTooLargeError(RequirementError):
    """Submitted or edited source content exceeds the intake limits."""


class InvalidRequirementVersionError(RequirementError):
    """Raised when a Requirement or draft version is invalid."""


class DuplicateRequirementStateError(RequirementError):
    """An operation cannot run for a requirement closed as a duplicate."""
