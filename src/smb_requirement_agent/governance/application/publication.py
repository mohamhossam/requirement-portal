"""What publishing an approved backlog to a work-item tracker sends (Slice 12).

The plan is built from the neutral export of one formally approved revision, so publication
sends exactly what export would. It names no tracker: where each item lands, and as which
work-item type, is the publisher adapter's business (AGENTS.md §9).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from smb_requirement_agent.governance.application.exports import (
    ExportArchitecture,
    ExportFeature,
    NeutralBacklogExport,
)

# A tracker title is a single line; longer titles are cut with an ellipsis.
TITLE_LIMIT = 255


class WorkItemKind(StrEnum):
    EPIC = "epic"
    FEATURE = "feature"
    STORY = "story"


@dataclass(frozen=True)
class AcceptanceCriterionText:
    given: str
    when: str
    then: str


@dataclass(frozen=True)
class PlannedWorkItem:
    """One backlog item as it will be published, with its parent's key."""

    key: str
    kind: WorkItemKind
    # "Epic", "Feature 2", "Story 2.3": how people find the item in the preview.
    label: str
    title: str
    # Labelled paragraphs, in order; the publisher renders them in its own markup.
    description: tuple[tuple[str, str], ...]
    acceptance_criteria: tuple[AcceptanceCriterionText, ...]
    parent_key: str | None
    # The one squad whose systems the Feature changes, or None when it names none or several.
    owning_squad_id: str | None
    owning_squad_name: str | None


@dataclass(frozen=True)
class PublicationPlan:
    requirement_id: str
    revision: int
    approval_fingerprint: str
    # Parents always come before their children.
    items: tuple[PlannedWorkItem, ...]

    def count(self, kind: WorkItemKind) -> int:
        return sum(item.kind is kind for item in self.items)


@dataclass(frozen=True)
class SquadLocation:
    squad_id: str
    location: str


@dataclass(frozen=True)
class PublicationTarget:
    """Where a publisher sends items, described for the people confirming it."""

    system: str
    project: str
    default_location: str
    # Facts a person checks before confirming, such as the organization and iteration.
    details: tuple[tuple[str, str], ...]
    squad_locations: tuple[SquadLocation, ...] = ()

    def location_for(self, squad_id: str | None) -> str:
        """Where an item owned by this squad lands; the default when the squad has no place."""
        return next(
            (item.location for item in self.squad_locations if item.squad_id == squad_id),
            self.default_location,
        )


@dataclass(frozen=True)
class PublishedWorkItem:
    """An item the tracker accepted: its own id and where a person opens it."""

    key: str
    external_id: str
    url: str


class PublicationStepStatus(StrEnum):
    PUBLISHED = "published"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"


@dataclass(frozen=True)
class PublicationStep:
    item: PlannedWorkItem
    status: PublicationStepStatus
    published: PublishedWorkItem | None = None
    error: str | None = None


class PublicationOutcome(StrEnum):
    PUBLISHED = "published"
    # Some items were created before one failed; they stay in the tracker.
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True)
class PublicationReport:
    plan: PublicationPlan
    target: PublicationTarget
    outcome: PublicationOutcome
    steps: tuple[PublicationStep, ...]


def publication_plan(document: NeutralBacklogExport) -> PublicationPlan:
    epic = document.epic
    items: list[PlannedWorkItem] = [
        PlannedWorkItem(
            key=epic.id,
            kind=WorkItemKind.EPIC,
            label="Epic",
            title=_title(epic.name),
            description=(("Outcome", epic.outcome), ("Business case", epic.business_case)),
            acceptance_criteria=(),
            parent_key=None,
            owning_squad_id=None,
            owning_squad_name=None,
        )
    ]
    for feature in epic.features:
        squad = _owning_squad(feature)
        squad_id, squad_name = squad if squad is not None else (None, None)
        items.append(
            PlannedWorkItem(
                key=feature.id,
                kind=WorkItemKind.FEATURE,
                label=f"Feature {feature.sequence}",
                title=_title(feature.name),
                description=(
                    ("Outcome", feature.outcome),
                    ("Delivery drop", feature.delivery_drop),
                    ("Split by", f"{feature.splitting_pattern}: {feature.splitting_rationale}"),
                ),
                acceptance_criteria=(),
                parent_key=epic.id,
                owning_squad_id=squad_id,
                owning_squad_name=squad_name,
            )
        )
        for story in feature.stories:
            items.append(
                PlannedWorkItem(
                    key=story.id,
                    kind=WorkItemKind.STORY,
                    label=f"Story {feature.sequence}.{story.sequence}",
                    title=_title(f"As a {story.role}, I want {story.action}"),
                    description=(("Story", story.voice),),
                    acceptance_criteria=tuple(
                        AcceptanceCriterionText(item.given, item.when, item.then)
                        for item in story.acceptance_criteria
                    ),
                    parent_key=feature.id,
                    # A Story lands where its Feature does, on the same squad's board.
                    owning_squad_id=squad_id,
                    owning_squad_name=squad_name,
                )
            )
    manifest = document.manifest
    return PublicationPlan(
        requirement_id=manifest.requirement_id,
        revision=manifest.breakdown_revision,
        approval_fingerprint=manifest.final_approval.subject_fingerprint,
        items=tuple(items),
    )


def _owning_squad(feature: ExportFeature) -> tuple[str, str] | None:
    """The squad that owns every system the Feature changes; None for none or several.

    Picking one of several squads would be a guess, so such a Feature goes to the default
    location for a person to route.
    """
    architecture: ExportArchitecture | None = feature.architecture
    if architecture is None:
        return None
    squads = {squad.id: squad.name for system in architecture.systems for squad in system.squads}
    if len(squads) != 1:
        return None
    return next(iter(squads.items()))


def _title(text: str) -> str:
    line = " ".join(text.split())
    if len(line) <= TITLE_LIMIT:
        return line
    return line[: TITLE_LIMIT - 1].rstrip() + "…"
