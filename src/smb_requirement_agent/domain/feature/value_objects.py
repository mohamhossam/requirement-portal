"""Value objects for the Feature aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from smb_requirement_agent.domain.feature.errors import InvalidFeatureContentError
from smb_requirement_agent.shared_kernel.generation import GenerationStatus, Provenance

# Aliases, not parallel definitions: a Feature's status and provenance are the
# shared ones, so a Feature status can never fail to compare equal to an Epic's.
FeatureStatus = GenerationStatus
FeatureProvenance = Provenance

__all__ = [
    "DeliveryDrop",
    "FeatureId",
    "FeatureName",
    "FeatureOutcome",
    "FeatureProvenance",
    "FeatureStatus",
    "SplittingPattern",
    "SplittingRationale",
]


def _normalised(value: str, field: str) -> str:
    """Strip surrounding whitespace, rejecting empty and blank input."""
    stripped = value.strip()
    if not stripped:
        raise InvalidFeatureContentError(f"Feature {field} must not be empty or blank.")
    return stripped


@dataclass(frozen=True)
class FeatureId:
    """Identifies a Feature within the system."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalised(self.value, "id"))


@dataclass(frozen=True)
class FeatureName:
    """The Feature's name."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalised(self.value, "name"))


@dataclass(frozen=True)
class FeatureOutcome:
    """The one measurable outcome the Feature delivers.

    Describes capability and benefit. Never written in user-story voice.
    """

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalised(self.value, "outcome"))


@dataclass(frozen=True)
class SplittingRationale:
    """Why this is a separate Feature rather than part of another."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalised(self.value, "splitting rationale"))


class SplittingPattern(Enum):
    """The strategy used to split this Feature out, per AGENTS.md section 6."""

    COMPONENT_SYSTEM = "component_system"
    JOURNEY_STAGE = "journey_stage"
    MVP_VS_LATER = "mvp_vs_later"
    CHANNEL = "channel"
    BUSINESS_VARIANT = "business_variant"


class DeliveryDrop(Enum):
    """Whether the Feature is core or a later increment.

    Numbered drops (Drop 2, Drop 3) are deferred until a slice needs them.
    """

    MVP = "mvp"
    LATER = "later"
