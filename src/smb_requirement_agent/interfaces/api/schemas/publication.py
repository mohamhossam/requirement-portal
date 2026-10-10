"""Publication preview and result transport schemas (Slice 12)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from smb_requirement_agent.governance.application.publication import (
    PlannedWorkItem,
    PublicationOutcome,
    PublicationPlan,
    PublicationReport,
    PublicationStepStatus,
    PublicationTarget,
    WorkItemKind,
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
    model_config = ConfigDict(frozen=True)


class PublicationPreviewResponse(BaseModel):
    requirement_id: str
    revision: int
    approval_fingerprint: str
    target: PublicationTargetResponse
    counts: PublicationCountsResponse
    items: list[PlannedWorkItemResponse]
    model_config = ConfigDict(frozen=True)


class PublishBreakdownRequest(BaseModel):
    # The final approval's fingerprint from the preview: the content the owner confirmed.
    approval_fingerprint: NonBlankIdentifier


class PublicationStepResponse(BaseModel):
    key: str
    kind: WorkItemKind
    label: str
    title: str
    status: PublicationStepStatus
    external_id: str | None
    url: str | None
    error: str | None
    model_config = ConfigDict(frozen=True)


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


def planned_item_response(
    item: PlannedWorkItem, target: PublicationTarget
) -> PlannedWorkItemResponse:
    return PlannedWorkItemResponse(
        key=item.key,
        kind=item.kind,
        label=item.label,
        title=item.title,
        parent_key=item.parent_key,
        acceptance_criteria_count=len(item.acceptance_criteria),
        owning_squad_name=item.owning_squad_name,
        location=target.location_for(item.owning_squad_id),
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
