"""Events the architecture impact mapping publishes (ADR-0103 §3)."""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.shared_kernel.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class ArchitectureImpactChanged(DomainEvent):
    """The breakdown's Features and Stories were mapped to the architecture again."""
