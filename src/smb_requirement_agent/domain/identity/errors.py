"""Identity and access invariant failures."""


class InvalidIdentityError(ValueError):
    """Actor or assignment content is invalid."""


class RequirementAccessConflictError(ValueError):
    """A requested ownership change conflicts with current access."""


class AuthorizationDeniedError(PermissionError):
    """The authenticated actor may not perform an operation."""
