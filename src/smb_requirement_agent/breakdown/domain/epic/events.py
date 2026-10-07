"""Events the Epic publishes (ADR-0103 §3)."""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.breakdown.domain.epic.value_objects import EpicId
from smb_requirement_agent.shared_kernel.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class EpicChanged(DomainEvent):
    """The Epic was regenerated or edited, so the Features under it no longer match it."""

    epic_id: EpicId
