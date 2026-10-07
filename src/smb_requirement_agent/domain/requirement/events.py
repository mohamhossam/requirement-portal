"""Events the Requirement context publishes (ADR-0103 §3)."""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.shared_kernel.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class RequirementRevised(DomainEvent):
    """The Requirement's source changed: its text, structured context or included documents."""
