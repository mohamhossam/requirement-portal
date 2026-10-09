"""The review lifecycle shared by every generated aggregate.

Epic and Feature are produced by an AI, reviewed by a human, and invalidated
when their source changes. The content differs; the rules do not:

- editing revokes approval, because the approval attested to content that no
  longer exists, and clears staleness, because a deliberate edit asserts the
  content reflects the current source;
- approval is idempotent and refused while stale;
- marking stale is idempotent and preserves content and status, so the first
  divergence is the one on record.

Stating those once means a change to the review rules cannot silently apply to
one aggregate and not the other. Each aggregate keeps its own error types, so
callers still catch a Feature error for a Feature.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Self

from smb_requirement_agent.shared_kernel.actions import ActionAvailability
from smb_requirement_agent.shared_kernel.approval import Approval, ApprovalDecision
from smb_requirement_agent.shared_kernel.errors import (
    InvalidApprovalContentError,
    InvalidGeneratedContentError,
)
from smb_requirement_agent.shared_kernel.lineage import SourceLineage
from smb_requirement_agent.shared_kernel.staleness import (
    Staleness,
    StaleReason,
    require_aware,
)


class GenerationStatus(Enum):
    """How far a generated aggregate has travelled through human review."""

    GENERATED = "generated"
    EDITED = "edited"
    NEEDS_REVISION = "needs_revision"
    APPROVED = "approved"


@dataclass(frozen=True)
class Provenance:
    """What produced an aggregate's content, and when.

    Carried unchanged through edits and approval so a reviewer can always tell
    what generated the text they are signing off on.
    """

    generated_at: datetime
    model: str
    prompt_version: str

    def __post_init__(self) -> None:
        require_aware(self.generated_at, "generated_at")
        for field, value in (("model", self.model), ("prompt_version", self.prompt_version)):
            if not value.strip():
                raise InvalidGeneratedContentError(f"Provenance {field} must not be blank.")
            object.__setattr__(self, field, value.strip())


@dataclass(frozen=True, kw_only=True)
class ReviewableGeneration:
    """Base for AI-generated content that a human reviews and approves.

    Subclasses add their own content fields and expose `edit`/`approve` with
    their own signatures and error types, delegating the mechanics here.
    """

    status: GenerationStatus
    provenance: Provenance
    staleness: Staleness | None = None
    approvals: tuple[Approval, ...] = ()
    version: int = 1
    source_lineage: tuple[SourceLineage, ...] = ()

    # How a reviewer names this aggregate ("Epic", "Feature", "Story").
    review_label: ClassVar[str]

    def __post_init__(self) -> None:
        if self.version < 1:
            raise InvalidGeneratedContentError("Generated-content version must be positive.")

    def approval_availability(self) -> ActionAvailability:
        """Approval is refused while stale and redundant once this version is approved."""
        if self.staleness is not None:
            return ActionAvailability.block(
                f"Reconcile this {self.review_label}: its source "
                f"{_SOURCE_LABELS[self.staleness.reason]} changed."
            )
        if self.status is GenerationStatus.APPROVED:
            return ActionAvailability.block(
                f"This {self.review_label} version is already approved. "
                "Edit or regenerate it before approving again."
            )
        return ActionAvailability.allow()

    def regeneration_availability(self) -> ActionAvailability:
        """Regeneration is always possible, but replacing human work must be confirmed."""
        if not self.is_human_owned:
            return ActionAvailability.allow()
        return ActionAvailability.allow(
            confirmation=f"This {self.review_label} has been {_STATUS_LABELS[self.status]}. "
            "Regenerating replaces its content and human review state."
        )

    @property
    def is_stale(self) -> bool:
        return self.staleness is not None

    @property
    def is_human_owned(self) -> bool:
        """True once a human has edited or approved the content.

        The predicate gating forced regeneration: generated-but-untouched
        content is free to replace, anything else is someone's work.
        """
        return self.status in (
            GenerationStatus.EDITED,
            GenerationStatus.NEEDS_REVISION,
            GenerationStatus.APPROVED,
        )

    def _edited(self, *, source_reconciled: bool = False, **content: Any) -> Self:
        """Apply new content, revoking approval without silently clearing staleness."""
        return replace(
            self,
            status=GenerationStatus.EDITED,
            staleness=None if source_reconciled else self.staleness,
            version=self.version + 1,
            **content,
        )

    def _approved(self, approval: Approval) -> Self:
        """Record a content-bound approval. Exact replays are idempotent."""
        if approval.decision is not ApprovalDecision.APPROVED:
            raise InvalidApprovalContentError(
                "An approval transition requires an approved decision."
            )
        if self.current_approval(approval.subject_fingerprint) is not None:
            return self
        return replace(
            self,
            status=GenerationStatus.APPROVED,
            approvals=(*self.approvals, approval),
            version=self.version + 1,
        )

    def _rejected(self, approval: Approval) -> Self:
        """Record a rejection while preserving content for deliberate revision."""
        if approval.decision is not ApprovalDecision.REJECTED:
            raise InvalidApprovalContentError(
                "A rejection transition requires a rejected decision."
            )
        if approval in self.approvals:
            return self
        return replace(
            self,
            status=GenerationStatus.NEEDS_REVISION,
            approvals=(*self.approvals, approval),
            version=self.version + 1,
        )

    def current_approval(self, fingerprint: str) -> Approval | None:
        if self.status is not GenerationStatus.APPROVED:
            return None
        latest = next(
            (
                item
                for item in reversed(self.approvals)
                if item.subject_fingerprint == fingerprint.strip()
            ),
            None,
        )
        return latest if latest is not None and latest.attests_to(fingerprint) else None

    def mark_stale(self, reason: StaleReason, at: datetime) -> Self:
        """Flag that the source changed, preserving content and status.

        Idempotent: an aggregate already stale keeps its original reason and
        timestamp, which record when it first diverged.
        """
        if self.is_stale:
            return self
        return replace(
            self,
            staleness=Staleness(reason=reason, since=at),
            version=self.version + 1,
        )


_SOURCE_LABELS = {
    StaleReason.REQUIREMENT_CHANGED: "requirement",
    StaleReason.EPIC_CHANGED: "Epic",
    StaleReason.FEATURE_CHANGED: "Feature",
}
_STATUS_LABELS = {
    GenerationStatus.GENERATED: "generated",
    GenerationStatus.EDITED: "edited",
    GenerationStatus.NEEDS_REVISION: "sent back for revision",
    GenerationStatus.APPROVED: "approved",
}
