"""Snapshot mappings for value types shared by several aggregates.

Actors, approvals, comments and the generation lifecycle.
"""

from __future__ import annotations

from datetime import datetime

from smb_requirement_agent.infrastructure.persistence.payload_fields import (
    JsonObject,
    json_object,
    nullable_text,
    optional_json_array,
    required_text,
)
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
    ActorSnapshot,
)
from smb_requirement_agent.shared_kernel.approval import (
    Approval,
    ApprovalDecision,
    ApprovalId,
    ApprovalTarget,
    ApprovalTargetKind,
    ReviewComment,
)
from smb_requirement_agent.shared_kernel.generation import GenerationStatus, Provenance
from smb_requirement_agent.shared_kernel.staleness import Staleness, StaleReason


def actor_to_payload(value: ActorProfile) -> JsonObject:
    return actor_fields_to_payload(value)


def actor_from_payload(data: JsonObject) -> ActorProfile:
    actor = actor_fields_from_payload(data, snapshot=False)
    if not isinstance(actor, ActorProfile):  # pragma: no cover - fixed by argument
        raise TypeError("Expected actor profile.")
    return actor


def actor_fields_to_payload(value: ActorProfile | ActorSnapshot) -> JsonObject:
    return {"id": value.id.value, "display_name": value.display_name, "email": value.email}


def actor_fields_from_payload(data: JsonObject, *, snapshot: bool) -> ActorProfile | ActorSnapshot:
    values = (
        ActorId(required_text(data, "id")),
        required_text(data, "display_name"),
        nullable_text(data, "email"),
    )
    return ActorSnapshot(*values) if snapshot else ActorProfile(*values)


def as_snapshot(value: ActorProfile | ActorSnapshot) -> ActorSnapshot:
    return value if isinstance(value, ActorSnapshot) else value.snapshot()


def generation_to_payload(
    status: GenerationStatus,
    provenance: Provenance,
    staleness: Staleness | None,
    approvals: tuple[Approval, ...],
) -> JsonObject:
    return {
        "status": status.value,
        "provenance": {
            "generated_at": provenance.generated_at.isoformat(),
            "model": provenance.model,
            "prompt_version": provenance.prompt_version,
        },
        "staleness": None
        if staleness is None
        else {"reason": staleness.reason.value, "since": staleness.since.isoformat()},
        "approvals": [approval_to_payload(item) for item in approvals],
    }


def generation_from_payload(
    data: JsonObject,
) -> tuple[GenerationStatus, Provenance, Staleness | None, tuple[Approval, ...]]:
    provenance_data = json_object(data["provenance"])
    raw_staleness = data.get("staleness")
    staleness = None
    if raw_staleness is not None:
        stale_data = json_object(raw_staleness)
        staleness = Staleness(
            StaleReason(required_text(stale_data, "reason")),
            datetime.fromisoformat(required_text(stale_data, "since")),
        )
    return (
        GenerationStatus(required_text(data, "status")),
        Provenance(
            generated_at=datetime.fromisoformat(required_text(provenance_data, "generated_at")),
            model=required_text(provenance_data, "model"),
            prompt_version=required_text(provenance_data, "prompt_version"),
        ),
        staleness,
        tuple(
            approval_from_payload(json_object(item))
            for item in optional_json_array(data, "approvals")
        ),
    )


def approval_to_payload(value: Approval) -> JsonObject:
    return {
        "id": value.id.value,
        "target": {"kind": value.target.kind.value, "item_id": value.target.item_id},
        "decision": value.decision.value,
        "subject_fingerprint": value.subject_fingerprint,
        "recorded_by": actor_fields_to_payload(value.recorded_by),
        "recorded_at": value.recorded_at.isoformat(),
        "rationale": value.rationale,
    }


def approval_from_payload(data: JsonObject) -> Approval:
    target = json_object(data["target"])
    return Approval(
        ApprovalId(required_text(data, "id")),
        ApprovalTarget(
            ApprovalTargetKind(required_text(target, "kind")),
            required_text(target, "item_id"),
        ),
        ApprovalDecision(required_text(data, "decision")),
        required_text(data, "subject_fingerprint"),
        required_actor_snapshot(data, "recorded_by"),
        datetime.fromisoformat(required_text(data, "recorded_at")),
        nullable_text(data, "rationale"),
    )


def comment_to_payload(value: ReviewComment) -> JsonObject:
    return {
        "id": value.id,
        "target": {"kind": value.target.kind.value, "item_id": value.target.item_id},
        "body": value.body,
        "recorded_by": actor_fields_to_payload(value.recorded_by),
        "recorded_at": value.recorded_at.isoformat(),
    }


def comment_from_payload(data: JsonObject) -> ReviewComment:
    target = json_object(data["target"])
    return ReviewComment(
        required_text(data, "id"),
        ApprovalTarget(
            ApprovalTargetKind(required_text(target, "kind")),
            required_text(target, "item_id"),
        ),
        required_text(data, "body"),
        required_actor_snapshot(data, "recorded_by"),
        datetime.fromisoformat(required_text(data, "recorded_at")),
    )


def optional_actor_snapshot(data: JsonObject, key: str) -> ActorSnapshot | None:
    value = data.get(key)
    if value is None:
        return None
    return as_snapshot(actor_fields_from_payload(json_object(value), snapshot=True))


def required_actor_snapshot(data: JsonObject, key: str) -> ActorSnapshot:
    return as_snapshot(actor_fields_from_payload(json_object(data[key]), snapshot=True))
