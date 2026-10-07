"""HTTP schemas for authenticated actors and Requirement access."""

from datetime import datetime

from pydantic import BaseModel, Field

from smb_requirement_agent.identity.domain.entities import AccessChangeKind, AssignmentRole
from smb_requirement_agent.infrastructure.config.options import IdentityProvider
from smb_requirement_agent.interfaces.api.schemas.bounds import (
    Identifier,
)


class ActorResponse(BaseModel):
    id: str
    display_name: str
    email: str | None
    roles: list[str] = Field(default_factory=list)


class LoginChoiceResponse(BaseModel):
    id: str
    label: str
    authorization_parameters: dict[str, str]


class IdentityConfigResponse(BaseModel):
    mode: IdentityProvider
    authority: str | None
    audience: str | None
    client_id: str | None
    scopes: str | None
    fake_actors: list[ActorResponse]
    login_choices: list[LoginChoiceResponse]


class AssignmentResponse(BaseModel):
    actor: ActorResponse
    role: AssignmentRole
    assigned_at: datetime
    assigned_by: ActorResponse


class AccessChangeResponse(BaseModel):
    kind: AccessChangeKind
    actor: ActorResponse
    performed_by: ActorResponse
    recorded_at: datetime


class RequirementAccessResponse(BaseModel):
    requirement_id: str
    version: int
    owner: AssignmentResponse | None
    reviewers: list[AssignmentResponse]
    changes: list[AccessChangeResponse]
    can_claim_owner: bool
    can_manage_assignments: bool
    can_confirm_analysis: bool
    can_export_approved_revisions: bool
    can_manage_content: bool
    can_govern: bool


class TransferOwnershipRequest(BaseModel):
    actor_id: Identifier
    expected_version: int


class AccessMutationRequest(BaseModel):
    expected_version: int
