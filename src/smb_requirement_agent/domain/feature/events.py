"""Events a Feature publishes (ADR-0103 §3)."""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.shared_kernel.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class FeatureChanged(DomainEvent):
    """The Feature was edited, so the Stories under it no longer match it."""

    feature_id: FeatureId
