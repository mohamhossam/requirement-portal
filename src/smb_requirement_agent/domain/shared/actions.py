"""Whether a reviewer may take an action now, stated once for use cases and clients.

The same predicate both refuses a command and tells a client why a control is
unavailable, so a browser never has to restate a review rule to grey out a
button, and the two cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.domain.shared.errors import InvalidGeneratedContentError


@dataclass(frozen=True)
class ActionAvailability:
    """An action's availability.

    `reason` explains a blocked action. `confirmation` marks an allowed action
    that replaces human work, which the caller must confirm explicitly.
    """

    allowed: bool
    reason: str | None = None
    confirmation: str | None = None

    def __post_init__(self) -> None:
        if self.allowed == (self.reason is not None):
            raise InvalidGeneratedContentError(
                "A blocked action needs a reason and an allowed action must not have one."
            )
        if not self.allowed and self.confirmation is not None:
            raise InvalidGeneratedContentError("A blocked action cannot ask for confirmation.")

    @classmethod
    def allow(cls, confirmation: str | None = None) -> ActionAvailability:
        return cls(allowed=True, confirmation=confirmation)

    @classmethod
    def block(cls, reason: str) -> ActionAvailability:
        return cls(allowed=False, reason=reason)
