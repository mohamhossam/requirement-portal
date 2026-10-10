"""Preview and explicitly publish one formally approved revision (Slice 12).

Only a revision export would accept is publishable, and only its owner may publish it,
after a preview: the confirmation must name the approval being published, so a request
built from an older preview is refused rather than sending other content. Items are
created parents first. When one fails, publication stops there: the items already
created stay in the tracker and are reported, and nothing under the failed item is sent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from smb_requirement_agent.governance.application.errors import (
    BreakdownRevisionNotPublishableError,
    PublicationConfirmationError,
    PublicationTargetError,
)
from smb_requirement_agent.governance.application.ports.backlog_publisher import (
    BacklogPublisherPort,
)
from smb_requirement_agent.governance.application.ports.breakdown_repository import (
    BreakdownRepositoryPort,
)
from smb_requirement_agent.governance.application.publication import (
    PublicationOutcome,
    PublicationPlan,
    PublicationReport,
    PublicationStep,
    PublicationStepStatus,
    PublicationTarget,
    PublishedWorkItem,
    publication_plan,
)
from smb_requirement_agent.governance.application.use_cases.export_breakdown import (
    approved_backlog_document,
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

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PublicationPreview:
    plan: PublicationPlan
    target: PublicationTarget


class _ApprovedPlans:
    """The publication plan of one exportable revision, after the access check."""

    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        authorization: RequirementAccessPort,
        revisions: BreakdownRepositoryPort,
    ) -> None:
        self._requirements = requirements
        self._authorization = authorization
        self._revisions = revisions

    def plan(
        self,
        requirement_id: RequirementId,
        revision_number: RevisionNumber,
        actor: ActorProfile,
        permission: RequirementPermission,
    ) -> PublicationPlan:
        if self._requirements.get(requirement_id) is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        self._authorization.require(requirement_id, actor, permission)
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


class PreviewPublication:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        authorization: RequirementAccessPort,
        revisions: BreakdownRepositoryPort,
        publisher: BacklogPublisherPort,
    ) -> None:
        self._plans = _ApprovedPlans(requirements, authorization, revisions)
        self._publisher = publisher

    def execute(
        self, requirement_id: RequirementId, revision_number: RevisionNumber, actor: ActorProfile
    ) -> PublicationPreview:
        plan = self._plans.plan(
            requirement_id, revision_number, actor, RequirementPermission.MEMBER
        )
        return PublicationPreview(plan, self._publisher.target())


class PublishBreakdown:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        authorization: RequirementAccessPort,
        revisions: BreakdownRepositoryPort,
        publisher: BacklogPublisherPort,
    ) -> None:
        self._plans = _ApprovedPlans(requirements, authorization, revisions)
        self._publisher = publisher

    def execute(
        self,
        requirement_id: RequirementId,
        revision_number: RevisionNumber,
        actor: ActorProfile,
        confirmed_fingerprint: str,
    ) -> PublicationReport:
        plan = self._plans.plan(requirement_id, revision_number, actor, RequirementPermission.OWNER)
        if confirmed_fingerprint != plan.approval_fingerprint:
            raise PublicationConfirmationError(
                "The confirmation does not match this revision's final approval; preview it again."
            )
        target = self._publisher.target()
        steps = self._publish(plan)
        report = PublicationReport(plan, target, _outcome(steps), steps)
        _log.info(
            "Breakdown revision published.",
            extra={
                "requirement_id": requirement_id.value,
                "revision": revision_number.value,
                "actor_id": actor.id.value,
                "outcome": report.outcome.value,
                "published": sum(s.status is PublicationStepStatus.PUBLISHED for s in steps),
                "planned": len(steps),
            },
        )
        return report

    def _publish(self, plan: PublicationPlan) -> tuple[PublicationStep, ...]:
        published: dict[str, PublishedWorkItem] = {}
        steps: list[PublicationStep] = []
        stopped = False
        for item in plan.items:
            if stopped:
                steps.append(PublicationStep(item, PublicationStepStatus.NOT_ATTEMPTED))
                continue
            parent = published[item.parent_key] if item.parent_key is not None else None
            try:
                created = self._publisher.create(item, parent)
            except PublicationTargetError as exc:
                steps.append(PublicationStep(item, PublicationStepStatus.FAILED, error=str(exc)))
                stopped = True
                continue
            published[item.key] = created
            steps.append(PublicationStep(item, PublicationStepStatus.PUBLISHED, created))
        return tuple(steps)


def _outcome(steps: tuple[PublicationStep, ...]) -> PublicationOutcome:
    created = sum(step.status is PublicationStepStatus.PUBLISHED for step in steps)
    if created == len(steps):
        return PublicationOutcome.PUBLISHED
    return PublicationOutcome.PARTIAL if created else PublicationOutcome.FAILED
