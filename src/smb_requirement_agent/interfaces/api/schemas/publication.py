"""Publication preview and result transport schemas (Slice 12)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from smb_requirement_agent.governance.application.publication import (
    ItemAction,
    PlannedWorkItem,
    PublicationPlan,
    PublicationReport,
    PublicationTarget,
    WorkItemKind,
)
from smb_requirement_agent.governance.application.use_cases.publish_breakdown import (
    PublicationOverview,
    PublicationPreview,
)
from smb_requirement_agent.governance.domain.publication.entities import (
    BacklogPublication,
    ExternalWorkItemMapping,
    ItemResult,
    PublicationOutcome,
    PublicationResult,
    PublicationStatus,
)
from smb_requirement_agent.interfaces.api.schemas.review import NonBlankIdentifier


class PublicationDetailResponse(BaseModel):
    label: str
    value: str
    model_config = ConfigDict(frozen=True)


class PublicationTargetResponse(BaseModel):
    system: str
    project: str
    default_location: str
    details: list[PublicationDetailResponse]
    model_config = ConfigDict(frozen=True)


class PublicationCountsResponse(BaseModel):
    epics: int
    features: int
    stories: int
    model_config = ConfigDict(frozen=True)


class PlannedWorkItemResponse(BaseModel):
    key: str
    kind: WorkItemKind
    label: str
    title: str
    parent_key: str | None
    acceptance_criteria_count: int
    owning_squad_name: str | None
    # Where the item lands in the target, such as an Azure DevOps area path.
    location: str
    # What publishing would do with it, given what was published before (Slice 13).
    action: ItemAction
    external_id: str | None
    url: str | None
    model_config = ConfigDict(frozen=True)


class WorkItemMappingResponse(BaseModel):
    local_key: str
    kind: str
    external_id: str
    url: str
    revision: int
    published_at: datetime
    model_config = ConfigDict(frozen=True)


class PublicationPreviewResponse(BaseModel):
    requirement_id: str
    revision: int
    approval_fingerprint: str
    target: PublicationTargetResponse
    counts: PublicationCountsResponse
    items: list[PlannedWorkItemResponse]
    status: PublicationStatus
    published_revision: int | None
    # Items published earlier that this revision no longer has; they stay in the tracker.
    removed: list[WorkItemMappingResponse]
    model_config = ConfigDict(frozen=True)


class PublishBreakdownRequest(BaseModel):
    # The final approval's fingerprint from the preview: the content the owner confirmed.
    approval_fingerprint: NonBlankIdentifier


class PublicationStepResponse(BaseModel):
    key: str
    kind: WorkItemKind
    label: str
    title: str
    status: ItemResult
    external_id: str | None
    url: str | None
    error: str | None
    model_config = ConfigDict(frozen=True)


class ItemOutcomeResponse(BaseModel):
    local_key: str
    result: ItemResult
    error: str | None
    model_config = ConfigDict(frozen=True)


class PublicationAttemptResponse(BaseModel):
    number: int
    revision: int
    actor_name: str
    started_at: datetime
    finished_at: datetime | None
    # None while the attempt runs.
    outcome: PublicationOutcome | None
    items: list[ItemOutcomeResponse]
    model_config = ConfigDict(frozen=True)


class PublicationStatusResponse(BaseModel):
    requirement_id: str
    status: PublicationStatus
    latest_approved_revision: int | None
    published_revision: int | None
    # Kept for tracing a delivery back to the promise; empty until analysis decides one.
    product_verdict: str | None
    product_impact_version: str | None
    mappings: list[WorkItemMappingResponse]
    # Newest first, at most ATTEMPT_LIMIT.
    attempts: list[PublicationAttemptResponse]
    model_config = ConfigDict(frozen=True)


ATTEMPT_LIMIT = 20


class PublicationReportResponse(BaseModel):
    requirement_id: str
    revision: int
    system: str
    project: str
    outcome: PublicationOutcome
    steps: list[PublicationStepResponse]
    model_config = ConfigDict(frozen=True)


def target_response(target: PublicationTarget) -> PublicationTargetResponse:
    return PublicationTargetResponse(
        system=target.system,
        project=target.project,
        default_location=target.default_location,
        details=[
            PublicationDetailResponse(label=label, value=value) for label, value in target.details
        ],
    )


def counts_response(plan: PublicationPlan) -> PublicationCountsResponse:
    return PublicationCountsResponse(
        epics=plan.count(WorkItemKind.EPIC),
        features=plan.count(WorkItemKind.FEATURE),
        stories=plan.count(WorkItemKind.STORY),
    )


def preview_response(preview: PublicationPreview) -> PublicationPreviewResponse:
    plan, target = preview.plan, preview.target
    return PublicationPreviewResponse(
        requirement_id=plan.requirement_id,
        revision=plan.revision,
        approval_fingerprint=plan.approval_fingerprint,
        target=target_response(target),
        counts=counts_response(plan),
        items=[
            planned_item_response(item, target, preview.actions[item.key], preview.existing)
            for item in plan.items
        ],
        status=preview.status,
        published_revision=preview.published_revision,
        removed=[mapping_response(item) for item in preview.removed],
    )


def mapping_response(mapping: ExternalWorkItemMapping) -> WorkItemMappingResponse:
    return WorkItemMappingResponse(
        local_key=mapping.local_key,
        kind=mapping.kind,
        external_id=mapping.external_id,
        url=mapping.url,
        revision=mapping.revision,
        published_at=mapping.published_at,
    )


def _attempt_response(attempt: PublicationResult) -> PublicationAttemptResponse:
    return PublicationAttemptResponse(
        number=attempt.number,
        revision=attempt.revision,
        actor_name=attempt.actor_name,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        outcome=attempt.outcome,
        items=[
            ItemOutcomeResponse(local_key=item.local_key, result=item.result, error=item.error)
            for item in attempt.items
        ],
    )


def status_response(
    requirement_id: str, overview: PublicationOverview
) -> PublicationStatusResponse:
    record: BacklogPublication | None = overview.publication
    return PublicationStatusResponse(
        requirement_id=requirement_id,
        status=overview.status,
        latest_approved_revision=overview.latest_approved_revision,
        published_revision=record.published_revision() if record else None,
        product_verdict=record.product_verdict if record else None,
        product_impact_version=record.product_impact_version if record else None,
        mappings=[mapping_response(item) for item in record.mappings] if record else [],
        attempts=(
            [_attempt_response(item) for item in reversed(record.results[-ATTEMPT_LIMIT:])]
            if record
            else []
        ),
    )


def planned_item_response(
    item: PlannedWorkItem,
    target: PublicationTarget,
    action: ItemAction,
    existing: dict[str, ExternalWorkItemMapping],
) -> PlannedWorkItemResponse:
    mapping = existing.get(item.key)
    return PlannedWorkItemResponse(
        key=item.key,
        kind=item.kind,
        label=item.label,
        title=item.title,
        parent_key=item.parent_key,
        acceptance_criteria_count=len(item.acceptance_criteria),
        owning_squad_name=item.owning_squad_name,
        location=target.location_for(item.owning_squad_id),
        action=action,
        external_id=mapping.external_id if mapping else None,
        url=mapping.url if mapping else None,
    )


def report_response(report: PublicationReport) -> PublicationReportResponse:
    return PublicationReportResponse(
        requirement_id=report.plan.requirement_id,
        revision=report.plan.revision,
        system=report.target.system,
        project=report.target.project,
        outcome=report.outcome,
        steps=[
            PublicationStepResponse(
                key=step.item.key,
                kind=step.item.kind,
                label=step.item.label,
                title=step.item.title,
                status=step.status,
                external_id=step.published.external_id if step.published else None,
                url=step.published.url if step.published else None,
                error=step.error,
            )
            for step in report.steps
        ],
    )
