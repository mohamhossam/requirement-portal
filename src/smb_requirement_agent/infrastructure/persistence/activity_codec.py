"""Shared persistence codec for derived activity and actor snapshots."""

from datetime import datetime
from typing import cast

from smb_requirement_agent.application.ports.activity import (
    ActivityAction,
    ActivityCategory,
    ActivityEvent,
    AuditSourceKind,
    AuditSourceReference,
)
from smb_requirement_agent.domain.shared.actors import ActorSnapshot
from smb_requirement_agent.domain.shared.identifiers import RequirementId
from smb_requirement_agent.infrastructure.persistence.payload_fields import JsonObject
from smb_requirement_agent.infrastructure.persistence.shared_payloads import actor_from_payload


def actor_to_payload(actor: ActorSnapshot) -> JsonObject:
    return {"id": actor.id.value, "display_name": actor.display_name, "email": actor.email}


def activity_to_payload(event: ActivityEvent) -> JsonObject:
    return {
        "id": event.id,
        "requirement_id": event.requirement_id.value,
        "requirement_title": event.requirement_title,
        "category": event.category.value,
        "action": event.action.value,
        "summary": event.summary,
        "occurred_at": event.occurred_at.isoformat(),
        "actor": actor_to_payload(event.actor) if event.actor else None,
        "target_id": event.target_id,
        "resource_path": event.resource_path,
        "sources": [
            {"kind": source.kind.value, "source_id": source.source_id} for source in event.sources
        ],
    }


def activity_from_payload(value: object) -> ActivityEvent | None:
    if value is None:
        return None
    payload = cast(JsonObject, value)
    actor_payload = payload.get("actor")
    actor = (
        actor_from_payload(cast(JsonObject, actor_payload)).snapshot()
        if isinstance(actor_payload, dict)
        else None
    )
    return ActivityEvent(
        id=str(payload["id"]),
        requirement_id=RequirementId(str(payload["requirement_id"])),
        requirement_title=str(payload["requirement_title"]),
        category=ActivityCategory(str(payload["category"])),
        action=ActivityAction(str(payload["action"])),
        summary=str(payload["summary"]),
        occurred_at=datetime.fromisoformat(str(payload["occurred_at"])),
        actor=actor,
        target_id=str(payload["target_id"]) if payload.get("target_id") else None,
        resource_path=str(payload["resource_path"]),
        sources=tuple(
            AuditSourceReference(AuditSourceKind(str(item["kind"])), str(item["source_id"]))
            for item in cast(list[JsonObject], payload.get("sources", []))
        ),
    )
