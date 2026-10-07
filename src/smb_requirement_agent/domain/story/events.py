"""Events a Feature's Stories publish (ADR-0103 §3)."""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.shared_kernel.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class StoriesChanged(DomainEvent):
    """A Feature's Stories were generated, edited, split, merged, regenerated or replaced."""

    feature_id: FeatureId
