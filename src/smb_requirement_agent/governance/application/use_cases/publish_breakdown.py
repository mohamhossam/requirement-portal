"""Preview, publish, republish and retry one formally approved revision (Slices 12-13).

Only a revision export would accept is publishable, and only its owner may publish it,
after a preview: the confirmation must name the approval being published, so a request
built from an older preview is refused rather than sending other content.

The Requirement's publication record says which local items already exist in the tracker
(Slice 13). Publishing creates the items it has no mapping for, updates those whose content
changed, and leaves the rest alone, so publishing twice never duplicates an item and a newer
approved revision updates what the earlier one created. Items are sent parents first; each
mapping is saved as soon as its item exists. When one is refused, the attempt stops there and
nothing under it is sent; a retry continues where it stopped. An attempt whose process ended
before it could record an item is found again by the item's marker, not created twice.
Items removed from the backlog are reported and left in the tracker: nothing is deleted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.governance.application.errors import (
    BreakdownRevisionNotPublishableError,
    PublicationConfirmationError,
    PublicationRetryNotAllowedError,
    PublicationTargetChangedError,
    PublicationTargetError,
)
from smb_requirement_agent.governance.application.ports.backlog_publisher import (
    BacklogPublisherPort,
)
from smb_requirement_agent.governance.application.ports.breakdown_repository import (
    BreakdownRepositoryPort,
)
from smb_requirement_agent.governance.application.ports.publication_repository import (
    PublicationRepositoryPort,
)
from smb_requirement_agent.governance.application.publication import (
    ItemAction,
    PlannedWorkItem,
    PublicationPlan,
    PublicationReport,
    PublicationStep,
    PublicationTarget,
    PublishedWorkItem,
    publication_plan,
)
from smb_requirement_agent.governance.application.use_cases.export_breakdown import (
    approved_backlog_document,
    is_exportable_revision,
)
from smb_requirement_agent.governance.domain.publication.entities import (
    BacklogPublication,
    ExternalWorkItemMapping,
    ItemOutcome,
    ItemResult,
    PublicationStatus,
)
from smb_requirement_agent.governance.domain.revision.entities import RevisionNumber
from smb_requirement_agent.governance.domain.revision.errors import RevisionNotFoundError
from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementAccessPort,
    RequirementPermission,
)
from smb_requirement_agent.requirements.application.errors import RequirementNotFoundError
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

# How long an attempt holds the Requirement before another may treat it as interrupted.
LEASE = timedelta(minutes=15)

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PublicationPreview:
    plan: PublicationPlan
    target: PublicationTarget
    status: PublicationStatus
    published_revision: int | None
    # What publishing would do with each planned item, by key.
    actions: dict[str, ItemAction]
    # Items published earlier that this revision no longer has; they stay in the tracker.
    removed: tuple[ExternalWorkItemMapping, ...]
    # The mappings of planned items already in the tracker, by key.
    existing: dict[str, ExternalWorkItemMapping]


@dataclass(frozen=True)
class PublicationOverview:
    status: PublicationStatus
    latest_approved_revision: int | None
    publication: BacklogPublication | None


class _Publications:
    """Plans, records and the access check the publication use cases share."""

    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        authorization: RequirementAccessPort,
        revisions: BreakdownRepositoryPort,
        publications: PublicationRepositoryPort,
        clock: ClockPort,
    ) -> None:
        self._requirements = requirements
        self._authorization = authorization
        self._revisions = revisions
        self.records = publications
        self.clock = clock

    def authorize(
        self, requirement_id: RequirementId, actor: ActorProfile, permission: RequirementPermission
    ) -> None:
        if self._requirements.get(requirement_id) is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        self._authorization.require(requirement_id, actor, permission)

    def plan(
        self, requirement_id: RequirementId, revision_number: RevisionNumber
    ) -> PublicationPlan:
        revision = self._revisions.get_breakdown_revision(requirement_id, revision_number)
        if revision is None:
            raise RevisionNotFoundError(
                f"Breakdown revision {revision_number.value} does not exist."
            )
        document = approved_backlog_document(revision)
        if document is None:
            raise BreakdownRevisionNotPublishableError(
                "Only a revision with a formal final approval and a Story under every Feature "
                "can be published."
            )
        return publication_plan(document)

    def latest_approved_revision(self, requirement_id: RequirementId) -> int | None:
        numbers = [
            revision.number.value
            for revision in self._revisions.list_breakdown_revisions(requirement_id)
            if is_exportable_revision(revision)
        ]
        return max(numbers, default=None)

    def record(
        self, requirement_id: RequirementId, target: PublicationTarget
    ) -> BacklogPublication | None:
        record = self.records.get(requirement_id)
        if record is not None and record.target_key != target.key:
            raise PublicationTargetChangedError(
                "This backlog was published to another tracker or project than the one set up "
                "now; publishing here would duplicate it."
            )
        return record


class PreviewPublication:
    def __init__(self, publications: _Publications, publisher: BacklogPublisherPort) -> None:
        self._publications = publications
        self._publisher = publisher

    def execute(
        self, requirement_id: RequirementId, revision_number: RevisionNumber, actor: ActorProfile
    ) -> PublicationPreview:
        publications = self._publications
        publications.authorize(requirement_id, actor, RequirementPermission.MEMBER)
        plan = publications.plan(requirement_id, revision_number)
        target = self._publisher.target()
        record = publications.record(requirement_id, target)
        keys = {item.key for item in plan.items}
        return PublicationPreview(
            plan=plan,
            target=target,
            status=(
                record.status(
                    publications.latest_approved_revision(requirement_id), publications.clock.now()
                )
                if record is not None
                else PublicationStatus.NOT_PUBLISHED
            ),
            published_revision=record.published_revision() if record is not None else None,
            actions={item.key: _action(item, record) for item in plan.items},
            removed=tuple(
                mapping
                for mapping in (record.mappings if record is not None else ())
                if mapping.local_key not in keys
            ),
            existing={
                mapping.local_key: mapping
                for mapping in (record.mappings if record is not None else ())
                if mapping.local_key in keys
            },
        )


class GetPublicationStatus:
    def __init__(self, publications: _Publications) -> None:
        self._publications = publications

    def execute(self, requirement_id: RequirementId, actor: ActorProfile) -> PublicationOverview:
        publications = self._publications
        publications.authorize(requirement_id, actor, RequirementPermission.MEMBER)
        record = publications.records.get(requirement_id)
        latest = publications.latest_approved_revision(requirement_id)
        status = (
            record.status(latest, publications.clock.now())
            if record is not None
            else PublicationStatus.NOT_PUBLISHED
        )
        return PublicationOverview(status, latest, record)


class PublishBreakdown:
    """Publish an approved revision: the first time, or as an update of an earlier one."""

    def __init__(self, publications: _Publications, publisher: BacklogPublisherPort) -> None:
        self._publications = publications
        self._run = _Run(publications, publisher)
        self._publisher = publisher

    def execute(
        self,
        requirement_id: RequirementId,
        revision_number: RevisionNumber,
        actor: ActorProfile,
        confirmed_fingerprint: str,
    ) -> PublicationReport:
        publications = self._publications
        publications.authorize(requirement_id, actor, RequirementPermission.OWNER)
        plan = publications.plan(requirement_id, revision_number)
        if confirmed_fingerprint != plan.approval_fingerprint:
            raise PublicationConfirmationError(
                "The confirmation does not match this revision's final approval; preview it again."
            )
        return self._run.run(plan, self._publisher.target(), actor)


class RetryFailedPublication:
    """Continue the latest attempt that did not finish, where that is safe.

    It is safe while the attempt's revision is still the latest with final approval: the
    owner confirmed exactly that content before. A newer approved revision is published
    with its own preview and confirmation instead.
    """

    def __init__(self, publications: _Publications, publisher: BacklogPublisherPort) -> None:
        self._publications = publications
        self._run = _Run(publications, publisher)
        self._publisher = publisher

    def execute(self, requirement_id: RequirementId, actor: ActorProfile) -> PublicationReport:
        publications = self._publications
        publications.authorize(requirement_id, actor, RequirementPermission.OWNER)
        target = self._publisher.target()
        record = publications.record(requirement_id, target)
        latest = record.latest if record is not None else None
        if record is None or latest is None:
            raise PublicationRetryNotAllowedError("Nothing has been published to retry.")
        if record.status(None, publications.clock.now()) is not PublicationStatus.INCOMPLETE:
            raise PublicationRetryNotAllowedError(
                "The latest publication is finished or still running; there is nothing to retry."
            )
        if (publications.latest_approved_revision(requirement_id) or 0) > latest.revision:
            raise PublicationRetryNotAllowedError(
                "A newer revision has final approval; preview and publish that one instead."
            )
        plan = publications.plan(requirement_id, RevisionNumber(latest.revision))
        return self._run.run(plan, target, actor)


class _Run:
    def __init__(self, publications: _Publications, publisher: BacklogPublisherPort) -> None:
        self._records = publications.records
        self._clock = publications.clock
        self._publications = publications
        self._publisher = publisher

    def run(
        self, plan: PublicationPlan, target: PublicationTarget, actor: ActorProfile
    ) -> PublicationReport:
        requirement_id = RequirementId(plan.requirement_id)
        record = self._publications.record(requirement_id, target)
        if record is None:
            record = BacklogPublication(requirement_id=requirement_id, target_key=target.key)
        now = self._clock.now()
        record = record.start(plan.revision, actor.id.value, actor.display_name, now, now + LEASE)
        self._records.save(record)
        recover = record.may_hold_unrecorded_items()
        steps: list[PublicationStep] = []
        stopped = False
        for item in plan.items:
            if stopped:
                record = record.record(ItemOutcome(item.key, ItemResult.NOT_ATTEMPTED))
                self._records.save(record)
                steps.append(PublicationStep(item, ItemResult.NOT_ATTEMPTED))
                continue
            try:
                result, published = self._send(item, record, recover)
            except PublicationTargetError as exc:
                record = record.record(ItemOutcome(item.key, ItemResult.FAILED, str(exc)))
                self._records.save(record)
                steps.append(PublicationStep(item, ItemResult.FAILED, error=str(exc)))
                stopped = True
                continue
            mapping = (
                ExternalWorkItemMapping(
                    local_key=item.key,
                    kind=item.kind.value,
                    external_id=published.external_id,
                    url=published.url,
                    content_fingerprint=item.content_fingerprint(),
                    revision=plan.revision,
                    published_at=self._clock.now(),
                )
                if result is not ItemResult.UNCHANGED
                else None
            )
            record = record.record(ItemOutcome(item.key, result), mapping)
            # Saved before the next item is sent, so a crash cannot lose a created item.
            self._records.save(record)
            steps.append(PublicationStep(item, result, published))
        record = record.finish(self._clock.now())
        self._records.save(record)
        latest = record.latest
        outcome = latest.outcome if latest is not None else None
        if outcome is None:  # pragma: no cover - finish() always closes the attempt
            raise RuntimeError("A finished attempt has an outcome.")
        report = PublicationReport(plan, target, outcome, tuple(steps))
        _log.info(
            "Breakdown revision published.",
            extra={
                "requirement_id": plan.requirement_id,
                "revision": plan.revision,
                "actor_id": actor.id.value,
                "outcome": outcome.value,
                "attempt": latest.number if latest is not None else None,
                "sent": sum(
                    step.status in (ItemResult.CREATED, ItemResult.UPDATED, ItemResult.RECOVERED)
                    for step in steps
                ),
                "planned": len(steps),
            },
        )
        return report

    def _send(
        self, item: PlannedWorkItem, record: BacklogPublication, recover: bool
    ) -> tuple[ItemResult, PublishedWorkItem]:
        mapping = record.mapping_for(item.key)
        if mapping is not None:
            existing = PublishedWorkItem(item.key, mapping.external_id, mapping.url)
            if mapping.content_fingerprint == item.content_fingerprint():
                return ItemResult.UNCHANGED, existing
            return ItemResult.UPDATED, self._publisher.update(mapping.external_id, item)
        if recover:
            found = self._publisher.find(item)
            if found is not None:
                return ItemResult.RECOVERED, self._publisher.update(found.external_id, item)
        parent = None
        if item.parent_key is not None:
            parent_mapping = record.mapping_for(item.parent_key)
            if parent_mapping is None:  # pragma: no cover - parents are sent first
                raise PublicationTargetError("The item's parent was not published.")
            parent = PublishedWorkItem(
                item.parent_key, parent_mapping.external_id, parent_mapping.url
            )
        return ItemResult.CREATED, self._publisher.create(item, parent)


def _action(item: PlannedWorkItem, record: BacklogPublication | None) -> ItemAction:
    mapping = record.mapping_for(item.key) if record is not None else None
    if mapping is None:
        return ItemAction.CREATE
    if mapping.content_fingerprint == item.content_fingerprint():
        return ItemAction.UNCHANGED
    return ItemAction.UPDATE


def build_publication_use_cases(
    requirements: RequirementRepositoryPort,
    authorization: RequirementAccessPort,
    revisions: BreakdownRepositoryPort,
    publications: PublicationRepositoryPort,
    clock: ClockPort,
    publisher: BacklogPublisherPort,
) -> tuple[PreviewPublication, PublishBreakdown, RetryFailedPublication, GetPublicationStatus]:
    shared = _Publications(requirements, authorization, revisions, publications, clock)
    return (
        PreviewPublication(shared, publisher),
        PublishBreakdown(shared, publisher),
        RetryFailedPublication(shared, publisher),
        GetPublicationStatus(shared),
    )
