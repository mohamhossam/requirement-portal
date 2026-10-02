"""HTTP transport schemas for the Epic API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from smb_requirement_agent.domain.shared.generation import GenerationStatus
from smb_requirement_agent.domain.shared.staleness import StaleReason
from smb_requirement_agent.interfaces.api.schemas.bounds import (
    Name,
    Text,
)
from smb_requirement_agent.interfaces.api.schemas.generation import ActionAvailabilityResponse
from smb_requirement_agent.interfaces.api.schemas.governance import ApprovalResponse


class EditEpicRequest(BaseModel):
    name: Name
    outcome: Text
    business_case: Text
    source_reconciled: bool = False
    expected_version: int


class ProvenanceResponse(BaseModel):
    generated_at: datetime
    model: str
    prompt_version: str

    model_config = ConfigDict(frozen=True, protected_namespaces=())


class StalenessResponse(BaseModel):
    reason: StaleReason
    since: datetime

    model_config = ConfigDict(frozen=True)


class EpicActionsResponse(BaseModel):
    approve: ActionAvailabilityResponse
    regenerate: ActionAvailabilityResponse
    generate_features: ActionAvailabilityResponse

    model_config = ConfigDict(frozen=True)


class EpicResponse(BaseModel):
    """The Epic and everything a reviewer needs to judge it in one call."""

    id: str
    version: int
    requirement_id: str
    name: str
    outcome: str
    business_case: str
    status: GenerationStatus
    provenance: ProvenanceResponse
    stale: StalenessResponse | None
    content_fingerprint: str
    current_approval: ApprovalResponse | None
    approval_history: list[ApprovalResponse]
    actions: EpicActionsResponse
    feature_context_token: str | None = None

    model_config = ConfigDict(frozen=True)
