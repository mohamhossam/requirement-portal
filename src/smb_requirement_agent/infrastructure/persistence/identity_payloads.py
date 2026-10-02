"""Snapshot mapping for Requirement access, reviewer assignments and draft ownership."""

from __future__ import annotations

from datetime import datetime

from smb_requirement_agent.domain.identity.entities import (
    AccessChange,
    AccessChangeKind,
    AssignmentRole,
    DraftOwnership,
    RequirementAccess,
    RequirementAssignment,
)
from smb_requirement_agent.domain.requirement.value_objects import (
    RequirementId,
)
from smb_requirement_agent.infrastructure.persistence.payload_fields import (
    JsonObject,
    json_array,
    json_object,
    optional_integer,
    required_text,
)
from smb_requirement_agent.infrastructure.persistence.shared_payloads import (
    actor_fields_from_payload,
    actor_fields_to_payload,
    as_snapshot,
)


def access_to_payload(value: RequirementAccess) -> JsonObject:
    return {
        "version": value.version,
        "requirement_id": value.requirement_id.value,
        "owner": _assignment_to_payload(value.owner) if value.owner else None,
        "reviewers": [_assignment_to_payload(item) for item in value.reviewers],
        "changes": [
            {
                "kind": item.kind.value,
                "actor": actor_fields_to_payload(item.actor),
                "performed_by": actor_fields_to_payload(item.performed_by),
                "recorded_at": item.recorded_at.isoformat(),
            }
            for item in value.changes
        ],
    }


def access_from_payload(data: JsonObject) -> RequirementAccess:
    return RequirementAccess(
        RequirementId(required_text(data, "requirement_id")),
        owner=(
            _assignment_from_payload(json_object(data["owner"]))
            if data.get("owner") is not None
            else None
        ),
        reviewers=tuple(
            _assignment_from_payload(json_object(item)) for item in json_array(data, "reviewers")
        ),
        changes=tuple(
            AccessChange(
                AccessChangeKind(required_text(json_object(item), "kind")),
                as_snapshot(
                    actor_fields_from_payload(
                        json_object(json_object(item)["actor"]), snapshot=True
                    )
                ),
                as_snapshot(
                    actor_fields_from_payload(
                        json_object(json_object(item)["performed_by"]), snapshot=True
                    )
                ),
                datetime.fromisoformat(required_text(json_object(item), "recorded_at")),
            )
            for item in json_array(data, "changes")
        ),
        version=optional_integer(data, "version", 1),
    )


def draft_ownership_to_payload(value: DraftOwnership) -> JsonObject:
    return {
        "draft_id": value.draft_id.value,
        "owner": _assignment_to_payload(value.owner) if value.owner else None,
    }


def draft_ownership_from_payload(data: JsonObject) -> DraftOwnership:
    return DraftOwnership(
        RequirementId(required_text(data, "draft_id")),
        _assignment_from_payload(json_object(data["owner"])) if data.get("owner") else None,
    )


def _assignment_to_payload(value: RequirementAssignment) -> JsonObject:
    return {
        "actor": actor_fields_to_payload(value.actor),
        "role": value.role.value,
        "assigned_at": value.assigned_at.isoformat(),
        "assigned_by": actor_fields_to_payload(value.assigned_by),
    }


def _assignment_from_payload(data: JsonObject) -> RequirementAssignment:
    return RequirementAssignment(
        as_snapshot(actor_fields_from_payload(json_object(data["actor"]), snapshot=True)),
        AssignmentRole(required_text(data, "role")),
        datetime.fromisoformat(required_text(data, "assigned_at")),
        as_snapshot(actor_fields_from_payload(json_object(data["assigned_by"]), snapshot=True)),
    )
