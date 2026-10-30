"""Outbound boundary for rendering a Business Requirements Document."""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.governance.application.specification import (
    RequirementSpecification,
    SpecificationFormat,
)


class SpecificationExportPort(Protocol):
    @property
    def format(self) -> SpecificationFormat: ...

    @property
    def extension(self) -> str: ...

    @property
    def media_type(self) -> str: ...

    def render(self, document: RequirementSpecification) -> bytes: ...
