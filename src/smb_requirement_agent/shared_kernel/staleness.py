"""Staleness, shared by every generated aggregate.

An aggregate derived from something else goes stale when that source changes.
The rule is always the same - flag, never destroy, so human review and approval
survive an upstream edit - so the concept lives here rather than being restated
per aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from smb_requirement_agent.shared_kernel.errors import InvalidGeneratedContentError


class StaleReason(Enum):
    """Why a generated aggregate no longer reflects its source."""

    REQUIREMENT_CHANGED = "requirement_changed"
    EPIC_CHANGED = "epic_changed"
    FEATURE_CHANGED = "feature_changed"


def require_aware(moment: datetime, field: str) -> datetime:
    """Reject naive datetimes, which compare and serialise ambiguously."""
    if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
        raise InvalidGeneratedContentError(f"{field} must be timezone-aware.")
    return moment


@dataclass(frozen=True)
class Staleness:
    """Records that an aggregate's source changed after it was produced."""

    reason: StaleReason
    since: datetime

    def __post_init__(self) -> None:
        require_aware(self.since, "staleness timestamp")
