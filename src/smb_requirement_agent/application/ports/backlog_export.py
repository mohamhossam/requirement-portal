"""Outbound boundary for rendering a neutral backlog package."""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.application.exports import ExportFormat, NeutralBacklogExport


class BacklogExportPort(Protocol):
    @property
    def format(self) -> ExportFormat: ...

    @property
    def extension(self) -> str: ...

    @property
    def media_type(self) -> str: ...

    def render(self, document: NeutralBacklogExport) -> bytes: ...
