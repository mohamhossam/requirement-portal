"""Stable JSON codec for Requirement and Requirement-draft current state."""

from __future__ import annotations

from datetime import datetime

from smb_requirement_agent.requirements.domain.requirement.entities import (
    Requirement,
    RequirementDraft,
)
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementContext,
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
    RequirementVersion,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

type JsonObject = dict[str, object]


def requirement_to_payload(value: Requirement) -> JsonObject:
    return {
        "id": value.id.value,
        "title": value.title.value,
        "description": value.description.value,
        "status": value.status.value,
        "desired_outcome": _context_value(value.desired_outcome),
        "customer_context": _context_value(value.customer_context),
        "channels": [item.value for item in value.channels],
        "systems": [item.value for item in value.systems],
        "business_rules": [item.value for item in value.business_rules],
        "constraints": [item.value for item in value.constraints],
        "version": value.version.value,
        "updated_at": value.updated_at.isoformat() if value.updated_at else None,
        "duplicate_of_requirement_id": (
            value.duplicate_of_requirement_id.value
            if value.duplicate_of_requirement_id is not None
            else None
        ),
    }


def requirement_from_payload(data: JsonObject) -> Requirement:
    return Requirement(
        id=RequirementId(_text(data, "id")),
        title=RequirementTitle(_text(data, "title")),
        description=RequirementDescription(_text(data, "description"), attachment_backed=True),
        status=RequirementStatus(_text(data, "status")),
        desired_outcome=_optional_context(data, "desired_outcome", fallback="description"),
        customer_context=_optional_context(data, "customer_context"),
        channels=_context_array(data, "channels"),
        systems=_context_array(data, "systems"),
        business_rules=_context_array(data, "business_rules"),
        constraints=_context_array(data, "constraints"),
        version=RequirementVersion(_optional_integer(data, "version", 1)),
        updated_at=_optional_datetime(data, "updated_at"),
        duplicate_of_requirement_id=(
            RequirementId(raw_duplicate)
            if (raw_duplicate := _nullable_text(data, "duplicate_of_requirement_id"))
            else None
        ),
    )


def requirement_draft_to_payload(value: RequirementDraft) -> JsonObject:
    return {
        "id": value.id.value,
        "title": value.title,
        "description": value.description,
        "desired_outcome": value.desired_outcome,
        "customer_context": value.customer_context,
        "channels": list(value.channels),
        "systems": list(value.systems),
        "business_rules": list(value.business_rules),
        "constraints": list(value.constraints),
        "version": value.version.value,
        "updated_at": value.updated_at.isoformat(),
    }


def requirement_draft_from_payload(data: JsonObject) -> RequirementDraft:
    return RequirementDraft(
        id=RequirementId(_text(data, "id")),
        title=_text(data, "title"),
        description=_text(data, "description"),
        desired_outcome=_text(data, "desired_outcome"),
        customer_context=_text(data, "customer_context"),
        channels=_text_array(data, "channels"),
        systems=_text_array(data, "systems"),
        business_rules=_text_array(data, "business_rules"),
        constraints=_text_array(data, "constraints"),
        version=RequirementVersion(_optional_integer(data, "version", 1)),
        updated_at=datetime.fromisoformat(_text(data, "updated_at")),
    )


def _text(data: JsonObject, key: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise TypeError(f"Expected {key!r} to be text.")
    return value


def _array(data: JsonObject, key: str) -> list[object]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise TypeError(f"Expected {key!r} to be an array.")
    return value


def _context_value(value: RequirementContext | None) -> str | None:
    return value.value if value is not None else None


def _optional_context(
    data: JsonObject, key: str, *, fallback: str | None = None
) -> RequirementContext | None:
    value = data.get(key)
    if key not in data and fallback is not None:
        value = data.get(fallback)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"Expected {key!r} to be text or null.")
    return RequirementContext(value)


def _context_array(data: JsonObject, key: str) -> tuple[RequirementContext, ...]:
    return tuple(RequirementContext(_item_text(item)) for item in _array(data, key))


def _text_array(data: JsonObject, key: str) -> tuple[str, ...]:
    return tuple(_item_text(item) for item in _array(data, key))


def _item_text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Expected array item to be text.")
    return value


def _optional_integer(data: JsonObject, key: str, default: int) -> int:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Expected {key!r} to be an integer.")
    return value


def _optional_datetime(data: JsonObject, key: str) -> datetime | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"Expected {key!r} to be an ISO datetime or null.")
    return datetime.fromisoformat(value)


def _nullable_text(data: JsonObject, key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"Expected {key!r} to be text or null.")
    return value
