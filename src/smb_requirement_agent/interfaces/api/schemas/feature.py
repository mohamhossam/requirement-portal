"""HTTP transport schemas for the Feature API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from smb_requirement_agent.domain.feature.value_objects import (
    DeliveryDrop,
    SplittingPattern,
)
from smb_requirement_agent.domain.shared.generation import GenerationStatus
from smb_requirement_agent.interfaces.api.schemas.architecture import ArchitectureImpactResponse
from smb_requirement_agent.interfaces.api.schemas.bounds import (
    Name,
    Text,
)
from smb_requirement_agent.interfaces.api.schemas.epic import ProvenanceResponse, StalenessResponse
from smb_requirement_agent.interfaces.api.schemas.generation import ActionAvailabilityResponse
from smb_requirement_agent.interfaces.api.schemas.governance import ApprovalResponse


class EditFeatureRequest(BaseModel):
    name: Name
    outcome: Text
    delivery_drop: DeliveryDrop
    splitting_pattern: SplittingPattern
    splitting_rationale: Text
    source_reconciled: bool = False
    expected_version: int


class FeatureActionsResponse(BaseModel):
    approve: ActionAvailabilityResponse
    generate_stories: ActionAvailabilityResponse

    model_config = ConfigDict(frozen=True)


class FeatureResponse(BaseModel):
    """One Feature and everything a reviewer needs to judge it."""

    id: str
    version: int
    epic_id: str
    name: str
    outcome: str
    delivery_drop: DeliveryDrop
    splitting_pattern: SplittingPattern
    splitting_rationale: str
    status: GenerationStatus
    provenance: ProvenanceResponse
    stale: StalenessResponse | None
    architecture: ArchitectureImpactResponse | None
    content_fingerprint: str
    current_approval: ApprovalResponse | None
    approval_history: list[ApprovalResponse]
    actions: FeatureActionsResponse
    story_context_token: str | None = None

    model_config = ConfigDict(frozen=True)


class FeatureSetResponse(BaseModel):
    """The Feature set for an Epic, in generation order."""

    epic_id: str
    features: list[FeatureResponse]
    set_version: int
    generation_context_token: str

    model_config = ConfigDict(frozen=True)
