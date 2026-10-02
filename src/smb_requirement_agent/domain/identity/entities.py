"""Provider-neutral actor identity and Requirement access aggregate."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from smb_requirement_agent.domain.identity.errors import (
    AuthorizationDeniedError,
    InvalidIdentityError,
    RequirementAccessConflictError,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.domain.shared.staleness import require_aware


def _text(value: str, field: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise InvalidIdentityError(f"Identity {field} must not be blank.")
    return stripped


@dataclass(frozen=True, order=True)
class ActorId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "actor id"))


@dataclass(frozen=True)
class ActorProfile:
    id: ActorId
    display_name: str
    email: str | None = None
    roles: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "display_name", _text(self.display_name, "display name"))
        if self.email is not None:
            email = self.email.strip()
            object.__setattr__(self, "email", email or None)
        roles = frozenset(role.strip() for role in self.roles if role.strip())
        object.__setattr__(self, "roles", roles)

    def snapshot(self) -> ActorSnapshot:
        return ActorSnapshot(self.id, self.display_name, self.email)


@dataclass(frozen=True)
class ActorSnapshot:
    id: ActorId
    display_name: str
    email: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "display_name", _text(self.display_name, "display name"))
        if self.email is not None:
            email = self.email.strip()
            object.__setattr__(self, "email", email or None)


class AssignmentRole(StrEnum):
    OWNER = "owner"
    REVIEWER = "reviewer"


class AccessChangeKind(StrEnum):
    CLAIMED = "claimed"
    TRANSFERRED = "transferred"
    REVIEWER_ASSIGNED = "reviewer_assigned"
    REVIEWER_REMOVED = "reviewer_removed"


@dataclass(frozen=True)
class RequirementAssignment:
    actor: ActorSnapshot
    role: AssignmentRole
    assigned_at: datetime
    assigned_by: ActorSnapshot

    def __post_init__(self) -> None:
        require_aware(self.assigned_at, "assignment assigned_at")


@dataclass(frozen=True)
class AccessChange:
    kind: AccessChangeKind
    actor: ActorSnapshot
    performed_by: ActorSnapshot
    recorded_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.recorded_at, "access change recorded_at")


@dataclass(frozen=True)
class RequirementAccess:
    requirement_id: RequirementId
    owner: RequirementAssignment | None = None
    reviewers: tuple[RequirementAssignment, ...] = ()
    changes: tuple[AccessChange, ...] = ()
    version: int = 1

    def __post_init__(self) -> None:
        if self.version < 1:
            raise InvalidIdentityError("Requirement access version must be positive.")
        if self.owner is not None and self.owner.role is not AssignmentRole.OWNER:
            raise InvalidIdentityError("Requirement owner assignment must use the owner role.")
        if any(item.role is not AssignmentRole.REVIEWER for item in self.reviewers):
            raise InvalidIdentityError("Requirement reviewers must use the reviewer role.")
        reviewer_ids = tuple(item.actor.id for item in self.reviewers)
        if len(reviewer_ids) != len(set(reviewer_ids)):
            raise InvalidIdentityError("Requirement reviewers must be unique.")
        if self.owner is not None and self.owner.actor.id in reviewer_ids:
            raise InvalidIdentityError("The Requirement owner cannot also be a reviewer.")

    def includes(self, actor_id: ActorId) -> bool:
        return (self.owner is not None and self.owner.actor.id == actor_id) or any(
            item.actor.id == actor_id for item in self.reviewers
        )

    def is_owner(self, actor_id: ActorId) -> bool:
        return self.owner is not None and self.owner.actor.id == actor_id

    def claim(self, actor: ActorProfile, at: datetime) -> RequirementAccess:
        require_aware(at, "ownership claimed_at")
        if self.owner is not None:
            if self.owner.actor.id == actor.id:
                return self
            raise RequirementAccessConflictError("This Requirement already has an owner.")
        snapshot = actor.snapshot()
        return replace(
            self,
            owner=RequirementAssignment(snapshot, AssignmentRole.OWNER, at, snapshot),
            changes=(*self.changes, AccessChange(AccessChangeKind.CLAIMED, snapshot, snapshot, at)),
            version=self.version + 1,
        )

    def transfer(
        self, current: ActorProfile, target: ActorProfile, at: datetime
    ) -> RequirementAccess:
        self.require_owner(current.id)
        require_aware(at, "ownership transferred_at")
        if current.id == target.id:
            return self
        target_snapshot = target.snapshot()
        actor_snapshot = current.snapshot()
        return replace(
            self,
            owner=RequirementAssignment(target_snapshot, AssignmentRole.OWNER, at, actor_snapshot),
            reviewers=tuple(item for item in self.reviewers if item.actor.id != target.id),
            changes=(
                *self.changes,
                AccessChange(AccessChangeKind.TRANSFERRED, target_snapshot, actor_snapshot, at),
            ),
            version=self.version + 1,
        )

    def assign_reviewer(
        self, current: ActorProfile, reviewer: ActorProfile, at: datetime
    ) -> RequirementAccess:
        self.require_owner(current.id)
        require_aware(at, "reviewer assigned_at")
        if self.owner is not None and reviewer.id == self.owner.actor.id:
            raise RequirementAccessConflictError("The Requirement owner cannot be a reviewer.")
        if any(item.actor.id == reviewer.id for item in self.reviewers):
            return self
        current_snapshot = current.snapshot()
        reviewer_snapshot = reviewer.snapshot()
        return replace(
            self,
            reviewers=(
                *self.reviewers,
                RequirementAssignment(
                    reviewer_snapshot, AssignmentRole.REVIEWER, at, current_snapshot
                ),
            ),
            changes=(
                *self.changes,
                AccessChange(
                    AccessChangeKind.REVIEWER_ASSIGNED,
                    reviewer_snapshot,
                    current_snapshot,
                    at,
                ),
            ),
            version=self.version + 1,
        )

    def remove_reviewer(
        self, current: ActorProfile, reviewer_id: ActorId, at: datetime
    ) -> RequirementAccess:
        self.require_owner(current.id)
        require_aware(at, "reviewer removed_at")
        reviewer = next((item for item in self.reviewers if item.actor.id == reviewer_id), None)
        if reviewer is None:
            return self
        current_snapshot = current.snapshot()
        return replace(
            self,
            reviewers=tuple(item for item in self.reviewers if item.actor.id != reviewer_id),
            changes=(
                *self.changes,
                AccessChange(
                    AccessChangeKind.REVIEWER_REMOVED,
                    reviewer.actor,
                    current_snapshot,
                    at,
                ),
            ),
            version=self.version + 1,
        )

    def require_owner(self, actor_id: ActorId) -> None:
        if not self.is_owner(actor_id):
            raise AuthorizationDeniedError("Only the Requirement owner may perform this action.")

    def require_member(self, actor_id: ActorId) -> None:
        if not self.includes(actor_id):
            raise AuthorizationDeniedError(
                "Only the Requirement owner or an assigned reviewer may perform this action."
            )


@dataclass(frozen=True)
class DraftOwnership:
    draft_id: RequirementId
    owner: RequirementAssignment | None = None

    def claim(self, actor: ActorProfile, at: datetime) -> DraftOwnership:
        require_aware(at, "draft ownership claimed_at")
        if self.owner is not None:
            if self.owner.actor.id == actor.id:
                return self
            raise RequirementAccessConflictError("This draft already has an owner.")
        snapshot = actor.snapshot()
        return replace(
            self,
            owner=RequirementAssignment(snapshot, AssignmentRole.OWNER, at, snapshot),
        )

    def require_owner(self, actor_id: ActorId) -> None:
        if self.owner is None or self.owner.actor.id != actor_id:
            raise AuthorizationDeniedError("Only the draft owner may perform this action.")
