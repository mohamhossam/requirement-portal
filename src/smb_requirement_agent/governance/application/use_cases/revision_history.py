"""Create, retrieve, and compare durable requirement revisions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.governance.application.ports.breakdown_repository import (
    BreakdownRepositoryPort,
)
from smb_requirement_agent.governance.application.use_cases.export_breakdown import (
    formal_final_approval,
)
from smb_requirement_agent.governance.domain.review.entities import (
    BreakdownReview,
    BreakdownStatus,
)
from smb_requirement_agent.governance.domain.revision.entities import (
    BreakdownRevision,
    RequirementRevision,
    RevisionNumber,
)
from smb_requirement_agent.governance.domain.revision.errors import RevisionNotFoundError
from smb_requirement_agent.identity.domain.entities import RequirementAccess
from smb_requirement_agent.requirements.application.errors import RequirementNotFoundError
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementStatus,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True)
class RevisionHistory:
    requirement_revisions: tuple[RequirementRevision, ...]
    breakdown_revisions: tuple[BreakdownRevision, ...]


@dataclass(frozen=True)
class BreakdownComparison:
    from_revision: RevisionNumber
    to_revision: RevisionNumber
    changes: tuple[str, ...]


class GetRevisionHistory:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        revisions: BreakdownRepositoryPort,
    ) -> None:
        self._requirements = requirements
        self._revisions = revisions

    def execute(self, requirement_id: RequirementId) -> RevisionHistory:
        _require_exists(self._requirements, requirement_id)
        return RevisionHistory(
            requirement_revisions=tuple(self._revisions.list_requirement_revisions(requirement_id)),
            breakdown_revisions=tuple(self._revisions.list_breakdown_revisions(requirement_id)),
        )


class CompareBreakdownVersions:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        revisions: BreakdownRepositoryPort,
    ) -> None:
        self._requirements = requirements
        self._revisions = revisions

    def execute(
        self,
        requirement_id: RequirementId,
        from_revision: RevisionNumber,
        to_revision: RevisionNumber,
    ) -> BreakdownComparison:
        _require_exists(self._requirements, requirement_id)
        before = self._revisions.get_breakdown_revision(requirement_id, from_revision)
        after = self._revisions.get_breakdown_revision(requirement_id, to_revision)
        if before is None or after is None:
            raise RevisionNotFoundError("One or both requested breakdown revisions do not exist.")
        return BreakdownComparison(from_revision, to_revision, _changes(before, after))


def _require_exists(requirements: RequirementRepositoryPort, requirement_id: RequirementId) -> None:
    if requirements.get(requirement_id) is None:
        raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")


def _changes(before: BreakdownRevision, after: BreakdownRevision) -> tuple[str, ...]:
    changes: list[str] = []
    if before.analysis != after.analysis:
        changes.append(
            "Requirement analysis, business-intent decisions, or human clarifications changed."
        )
    if before.epic != after.epic:
        changes.append("Epic content, review state, or staleness changed.")
    before_features = {item.id.value: item for item in before.features}
    after_features = {item.id.value: item for item in after.features}
    added = sorted(after_features.keys() - before_features.keys())
    removed = sorted(before_features.keys() - after_features.keys())
    edited = sorted(
        key
        for key in before_features.keys() & after_features.keys()
        if before_features[key] != after_features[key]
    )
    if added:
        changes.append(f"Features added: {', '.join(added)}.")
    if removed:
        changes.append(f"Features removed: {', '.join(removed)}.")
    if edited:
        changes.append(f"Features changed: {', '.join(edited)}.")
    before_stories = {item.id.value: item for item in before.stories}
    after_stories = {item.id.value: item for item in after.stories}
    stories_added = sorted(after_stories.keys() - before_stories.keys())
    stories_removed = sorted(before_stories.keys() - after_stories.keys())
    stories_edited = sorted(
        key
        for key in before_stories.keys() & after_stories.keys()
        if before_stories[key] != after_stories[key]
    )
    if stories_added:
        changes.append(f"Stories added: {', '.join(stories_added)}.")
    if stories_removed:
        changes.append(f"Stories removed: {', '.join(stories_removed)}.")
    if stories_edited:
        changes.append(f"Stories changed: {', '.join(stories_edited)}.")
    if before.review != after.review:
        changes.append(
            "Breakdown review flags, evidence, decisions, approvals, or comments changed."
        )
    return tuple(changes or ["No content changes."])


# --- What a revision changed, in a few words (ADR-0119 Amendment 1) ---------------------------

_REQUIREMENT_FIELDS: tuple[tuple[str, Callable[[Requirement], object]], ...] = (
    ("title", lambda item: item.title.value),
    ("description", lambda item: item.description.value),
    (
        "desired outcome",
        lambda item: item.desired_outcome.value if item.desired_outcome is not None else None,
    ),
    (
        "customer context",
        lambda item: item.customer_context.value if item.customer_context is not None else None,
    ),
    ("channels", lambda item: tuple(value.value for value in item.channels)),
    ("systems", lambda item: tuple(value.value for value in item.systems)),
    ("business rules", lambda item: tuple(value.value for value in item.business_rules)),
    ("constraints", lambda item: tuple(value.value for value in item.constraints)),
    (
        "current state",
        lambda item: item.current_state.value if item.current_state is not None else None,
    ),
    (
        "proposed state",
        lambda item: item.proposed_state.value if item.proposed_state is not None else None,
    ),
    ("out of scope", lambda item: tuple(value.value for value in item.out_of_scope)),
)


def describe_requirement_revision(
    before: RequirementRevision | None, after: RequirementRevision
) -> str:
    """Label a requirement revision by what changed since the one before it."""
    if before is None:
        return "Need captured"
    changes: list[str] = []
    edited = [
        name
        for name, read in _REQUIREMENT_FIELDS
        if read(before.requirement) != read(after.requirement)
    ]
    if edited:
        changes.append(f"Need edited: {', '.join(edited)}")
    if (
        before.requirement.status is not RequirementStatus.DUPLICATE
        and after.requirement.status is RequirementStatus.DUPLICATE
    ):
        changes.append("Closed as duplicate")
    if not changes and _team(before.access) != _team(after.access):
        changes.append("Team changed")
    return "; ".join(changes) or "Recorded again"


def describe_breakdown_revision(before: BreakdownRevision | None, after: BreakdownRevision) -> str:
    """Label a breakdown revision by what changed since the one before it."""
    changes: list[str] = []
    changes += _analysis_summary(before.analysis if before is not None else None, after.analysis)
    changes += _epic_summary(before.epic if before is not None else None, after.epic)
    changes += _items_summary(
        "Features",
        {item.id.value: item for item in (before.features if before is not None else ())},
        {item.id.value: item for item in after.features},
    )
    changes += _items_summary(
        "Stories",
        {item.id.value: item for item in (before.stories if before is not None else ())},
        {item.id.value: item for item in after.stories},
    )
    changes += _review_summary(before, after)
    return "; ".join(changes) or ("Recorded" if before is None else "Recorded again")


def _team(access: RequirementAccess | None) -> tuple[str | None, frozenset[str]]:
    if access is None:
        return (None, frozenset())
    return (
        access.owner.actor.id.value if access.owner is not None else None,
        frozenset(item.actor.id.value for item in access.reviewers),
    )


def _analysis_summary(
    before: RequirementAnalysis | None, after: RequirementAnalysis | None
) -> list[str]:
    if after is None:
        return ["Analysis discarded"] if before is not None else []
    if before is None:
        return [f"Analysis generated, round {after.round_number or 1}"]
    changes: list[str] = []
    if before.confirmed_at is None and after.confirmed_at is not None:
        changes.append("Analysis confirmed")
    if (after.round_number or 1) > (before.round_number or 1):
        changes.append(f"Analysis re-run, round {after.round_number or 1}")
    if len(after.clarifications) > len(before.clarifications):
        changes.append("Clarification answered")
    if tuple(item.status for item in after.intent_proposals) != tuple(
        item.status for item in before.intent_proposals
    ):
        changes.append("Business-intent decision recorded")
    before_decision = before.product_impact.decision if before.product_impact else None
    after_decision = after.product_impact.decision if after.product_impact else None
    if before_decision is None and after_decision is not None:
        changes.append("Product verdict decided")
    if not changes and before != after:
        changes.append("Analysis changed")
    return changes


def _epic_summary(before: Epic | None, after: Epic | None) -> list[str]:
    if before is None and after is not None:
        return ["Epic generated"]
    if before is not None and after is None:
        return ["Epic removed"]
    if before != after:
        return ["Epic changed"]
    return []


def _items_summary(name: str, before: dict[str, object], after: dict[str, object]) -> list[str]:
    if not before and after:
        return [f"{name} generated ({len(after)})"]
    if before and not after:
        return [f"{name} removed"]
    if before != after:
        return [f"{name} changed"]
    return []


def _review_summary(before: BreakdownRevision | None, after: BreakdownRevision) -> list[str]:
    previous: BreakdownReview | None = before.review if before is not None else None
    current = after.review
    if current is None:
        return ["Review discarded"] if previous is not None else []
    if previous is None:
        return ["Review generated"]
    changes: list[str] = []
    approved_now = formal_final_approval(after) is not None and (
        before is None or formal_final_approval(before) is None
    )
    if approved_now:
        changes.append("Final approval recorded")
    if previous.status is not current.status:
        if current.status is BreakdownStatus.UNDER_REVIEW:
            changes.append("Submitted for review")
        elif current.status is BreakdownStatus.NEEDS_REVISION:
            changes.append("Revision requested")
    if not approved_now and len(current.approvals) > len(previous.approvals):
        changes.append("Approval recorded")
    if len(current.decisions) > len(previous.decisions):
        changes.append("Review decision recorded")
    if len(current.comments) > len(previous.comments):
        changes.append("Comment added")
    if not changes and previous != current:
        changes.append("Review changed")
    return changes
