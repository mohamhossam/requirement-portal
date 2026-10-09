"""Which model-backed actions are available now (they run as jobs, ADR-0105)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from smb_requirement_agent.shared_kernel.actions import ActionAvailability


class ActionAvailabilityResponse(BaseModel):
    """Whether the caller's next action is available, and why not.

    `confirmation` is set when the action is allowed but replaces human work;
    the client must show it and send `force` to proceed. Authorization is not
    evaluated here: a non-member still receives 403 from the action itself.
    """

    allowed: bool
    reason: str | None
    confirmation: str | None
    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_domain(cls, availability: ActionAvailability) -> ActionAvailabilityResponse:
        return cls(
            allowed=availability.allowed,
            reason=availability.reason,
            confirmation=availability.confirmation,
        )
