"""Typed requests for model-backed mutations, and which of them are available now."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from smb_requirement_agent.domain.shared.actions import ActionAvailability
from smb_requirement_agent.interfaces.api.schemas.bounds import MAX_IDENTIFIER_CHARACTERS


class GenerationRequest(BaseModel):
    context_token: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    force: bool = False
    model_config = ConfigDict(frozen=True)


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
