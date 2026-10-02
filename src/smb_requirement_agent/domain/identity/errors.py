"""Identity and access invariant failures.

`InvalidIdentityError` is platform-kernel's, re-exported (ADR-0100).
"""

from smb_kernel.identity.actor import InvalidIdentityError as InvalidIdentityError


class RequirementAccessConflictError(ValueError):
    """A requested ownership change conflicts with current access."""


class AuthorizationDeniedError(PermissionError):
    """The authenticated actor may not perform an operation."""
