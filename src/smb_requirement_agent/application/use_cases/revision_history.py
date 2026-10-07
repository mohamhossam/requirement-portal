"""Create, retrieve, and compare durable requirement revisions."""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.application.errors import RequirementNotFoundError
from smb_requirement_agent.application.ports.breakdown_repository import BreakdownRepositoryPort
from smb_requirement_agent.application.ports.requirement_repository import RequirementRepositoryPort
from smb_requirement_agent.domain.revision.entities import (
    BreakdownRevision,
    RequirementRevision,
    RevisionNumber,
)
from smb_requirement_agent.domain.revision.errors import RevisionNotFoundError
from smb_requirement_agent.domain.shared.identifiers import RequirementId


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
