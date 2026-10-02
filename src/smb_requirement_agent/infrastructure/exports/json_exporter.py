"""Deterministic UTF-8 JSON adapter for the neutral export contract."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from typing import Any

from smb_requirement_agent.application.exports import ExportFormat, NeutralBacklogExport


class JsonBacklogExporter:
    @property
    def format(self) -> ExportFormat:
        return ExportFormat.JSON

    @property
    def extension(self) -> str:
        return "json"

    @property
    def media_type(self) -> str:
        return "application/json"

    def render(self, document: NeutralBacklogExport) -> bytes:
        return (json.dumps(_primitive(document), ensure_ascii=False, indent=2) + "\n").encode()


def _primitive(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _primitive(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    return value
