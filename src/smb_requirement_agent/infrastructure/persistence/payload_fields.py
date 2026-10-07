"""Typed field access for JSON snapshots: each helper fails loudly on a malformed payload."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from smb_requirement_agent.domain.requirement.value_objects import RequirementContext
from smb_requirement_agent.domain.shared.identifiers import RequirementId

type JsonObject = dict[str, object]


def required_text(data: JsonObject, key: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise TypeError(f"Snapshot field {key!r} must be text.")
    return value


def item_text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Snapshot array item must be text.")
    return value


def json_object(value: object) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError("Snapshot value must be an object.")
    return cast(JsonObject, value)


def json_array(data: JsonObject, key: str) -> list[object]:
    value = data[key]
    if not isinstance(value, list):
        raise TypeError(f"Snapshot field {key!r} must be an array.")
    return cast(list[object], value)


def optional_json_array(data: JsonObject, key: str) -> list[object]:
    return json_array(data, key) if key in data else []


def context_value(value: RequirementContext | None) -> str | None:
    return value.value if value is not None else None


def optional_context(
    data: JsonObject, key: str, *, fallback: str | None = None
) -> RequirementContext | None:
    value = data.get(key)
    if key not in data and fallback is not None:
        value = data.get(fallback)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"Snapshot field {key!r} must be text or null.")
    return RequirementContext(value) if value.strip() else None


def context_array(data: JsonObject, key: str) -> tuple[RequirementContext, ...]:
    if key not in data:
        return ()
    return tuple(RequirementContext(item) for item in text_array(data, key))


def text_array(data: JsonObject, key: str) -> tuple[str, ...]:
    return tuple(item_text(item) for item in json_array(data, key))


def optional_datetime(data: JsonObject, key: str) -> datetime | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"Snapshot field {key!r} must be text or null.")
    return datetime.fromisoformat(value)


def optional_requirement_id(data: JsonObject, key: str) -> RequirementId | None:
    value = data.get(key)
    return RequirementId(item_text(value)) if value is not None else None


def nullable_text(data: JsonObject, key: str) -> str | None:
    value = data.get(key)
    return item_text(value) if value is not None else None


def integer_field(data: JsonObject, key: str) -> int:
    value = data[key]
    if not isinstance(value, int):
        raise TypeError(f"Snapshot field {key!r} must be an integer.")
    return value


def optional_integer(data: JsonObject, key: str, default: int) -> int:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Snapshot field {key!r} must be an integer.")
    return value


def boolean_field(data: JsonObject, key: str) -> bool:
    value = data[key]
    if not isinstance(value, bool):
        raise TypeError(f"Snapshot field {key!r} must be a boolean.")
    return value
