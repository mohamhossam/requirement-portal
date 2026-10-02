"""Provider-neutral, immutable human governance records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from smb_requirement_agent.domain.identity.entities import ActorSnapshot
from smb_requirement_agent.domain.shared.errors import InvalidApprovalContentError
from smb_requirement_agent.domain.shared.staleness import require_aware


def _text(value: str, field: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise InvalidApprovalContentError(f"Approval {field} must not be blank.")
    return stripped


@dataclass(frozen=True, order=True)
class ApprovalId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "id"))


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalTargetKind(StrEnum):
    BREAKDOWN = "breakdown"
    EPIC = "epic"
    FEATURE = "feature"
    STORY = "story"
    FLAG = "flag"


@dataclass(frozen=True)
class ApprovalTarget:
    kind: ApprovalTargetKind
    item_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", _text(self.item_id, "target id"))


@dataclass(frozen=True)
class Approval:
    id: ApprovalId
    target: ApprovalTarget
    decision: ApprovalDecision
    subject_fingerprint: str
    recorded_by: ActorSnapshot
    recorded_at: datetime
    rationale: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "subject_fingerprint",
            _text(self.subject_fingerprint, "subject fingerprint"),
        )
        require_aware(self.recorded_at, "approval recorded_at")
        rationale = self.rationale.strip() if self.rationale is not None else None
        object.__setattr__(self, "rationale", rationale or None)
        if self.decision is ApprovalDecision.REJECTED and self.rationale is None:
            raise InvalidApprovalContentError("A rejection requires a rationale.")

    def attests_to(self, fingerprint: str) -> bool:
        return (
            self.decision is ApprovalDecision.APPROVED
            and self.subject_fingerprint == fingerprint.strip()
        )


@dataclass(frozen=True)
class ReviewComment:
    id: str
    target: ApprovalTarget
    body: str
    recorded_by: ActorSnapshot
    recorded_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "comment id"))
        object.__setattr__(self, "body", _text(self.body, "comment body"))
        require_aware(self.recorded_at, "review comment recorded_at")
