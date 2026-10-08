"""Authenticated portfolio activity, operational reports, and saved views."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime

from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    get_list_activity,
    get_operational_report,
    get_saved_views,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.routes.identity import actor_response
from smb_requirement_agent.interfaces.api.schemas.activity import (
    ActivityEventResponse,
    ActivityListResponse,
    AuditSourceResponse,
    BlockerResponse,
    ClarificationMetricsResponse,
    MetricCountResponse,
    OperationalReportResponse,
    SavedViewCreateRequest,
    SavedViewCriteriaRequest,
    SavedViewResponse,
    SavedViewUpdateRequest,
    WeeklyMetricsResponse,
)
from smb_requirement_agent.reporting.application.ports.activity import (
    ActivityAction,
    ActivityCategory,
    ActivityEvent,
    AuditSourceReference,
)
from smb_requirement_agent.reporting.application.ports.saved_views import (
    SavedRequirementView,
    SavedViewCriteria,
)
from smb_requirement_agent.reporting.application.use_cases.activity_reporting import (
    ActivityQuery,
    GetOperationalReport,
    ListActivity,
    MetricCount,
)
from smb_requirement_agent.reporting.application.use_cases.saved_views import SavedViews
from smb_requirement_agent.shared_kernel.actors import ActorId
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

activity_router = APIRouter(
    prefix="/activity",
    tags=["activity"],
    dependencies=[Depends(require_authenticated_actor)],
)
report_router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(require_authenticated_actor)],
)
saved_view_router = APIRouter(
    prefix="/saved-views",
    tags=["saved-views"],
    dependencies=[Depends(require_authenticated_actor)],
)


def _source(value: AuditSourceReference) -> AuditSourceResponse:
    return AuditSourceResponse(kind=value.kind, source_id=value.source_id)


def activity_response(value: ActivityEvent) -> ActivityEventResponse:
    return ActivityEventResponse(
        id=value.id,
        requirement_id=value.requirement_id.value,
        requirement_title=value.requirement_title,
        category=value.category,
        action=value.action,
        summary=value.summary,
        occurred_at=value.occurred_at,
        actor=actor_response(value.actor) if value.actor else None,
        target_id=value.target_id,
        resource_path=value.resource_path,
        sources=[_source(item) for item in value.sources],
    )


@activity_router.get("", response_model=ActivityListResponse)
def list_activity(
    use_case: Annotated[ListActivity, Depends(get_list_activity)],
    requirement_id: str | None = None,
    category: Annotated[list[ActivityCategory] | None, Query()] = None,
    action: Annotated[list[ActivityAction] | None, Query()] = None,
    actor_id: str | None = None,
    occurred_from: AwareDatetime | None = None,
    occurred_before: AwareDatetime | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ActivityListResponse:
    result = use_case.execute(
        ActivityQuery(
            RequirementId(requirement_id) if requirement_id else None,
            frozenset(category or []),
            frozenset(action or []),
            ActorId(actor_id) if actor_id else None,
            occurred_from,
            occurred_before,
            offset,
            limit,
        )
    )
    return ActivityListResponse(
        items=[activity_response(item) for item in result.items],
        total=result.total,
        offset=result.offset,
        limit=result.limit,
        has_more=result.has_more,
    )


def _metric(value: MetricCount) -> MetricCountResponse:
    return MetricCountResponse(value=value.value, evidence_event_ids=list(value.evidence_event_ids))


@report_router.get("/operational", response_model=OperationalReportResponse)
def operational_report(
    use_case: Annotated[GetOperationalReport, Depends(get_operational_report)],
    weeks: Annotated[int, Query()] = 12,
) -> OperationalReportResponse:
    report = use_case.execute(weeks)
    return OperationalReportResponse(
        generated_at=report.generated_at,
        window_start=report.window_start,
        window_end=report.window_end,
        weeks=report.weeks,
        weekly=[
            WeeklyMetricsResponse(
                week_start=item.week_start,
                week_end=item.week_end,
                requirements_created=_metric(item.requirements_created),
                analysis_rounds=_metric(item.analysis_rounds),
                clarifications_resolved=_metric(item.clarifications_resolved),
                artifact_approvals=_metric(item.artifact_approvals),
                breakdown_approvals=_metric(item.breakdown_approvals),
            )
            for item in report.weekly
        ],
        clarification=ClarificationMetricsResponse(
            opened=_metric(report.clarification.opened),
            resolved=_metric(report.clarification.resolved),
            resolution_percentage=report.clarification.resolution_percentage,
            median_resolution_hours=report.clarification.median_resolution_hours,
        ),
        oldest_blockers=[
            BlockerResponse(
                id=item.id,
                requirement_id=item.requirement_id.value,
                requirement_title=item.requirement_title,
                title=item.title,
                opened_at=item.opened_at,
                actor=actor_response(item.actor) if item.actor else None,
                resource_path=item.resource_path,
                source=_source(item.source),
            )
            for item in report.oldest_blockers
        ],
    )


def _criteria(value: SavedViewCriteriaRequest) -> SavedViewCriteria:
    return SavedViewCriteria(
        value.query,
        tuple(value.workflow_statuses),
        value.sort,
        ActorId(value.owner_id) if value.owner_id else None,
        value.assigned_to_me,
    )


def _saved_view(value: SavedRequirementView) -> SavedViewResponse:
    return SavedViewResponse(
        id=value.id,
        name=value.name,
        criteria=SavedViewCriteriaRequest(
            query=value.criteria.query,
            workflow_statuses=list(value.criteria.workflow_statuses),
            sort=value.criteria.sort,
            owner_id=value.criteria.owner_id.value if value.criteria.owner_id else None,
            assigned_to_me=value.criteria.assigned_to_me,
        ),
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


@saved_view_router.get("", response_model=list[SavedViewResponse])
def list_saved_views(
    actor: CurrentActorDep,
    use_case: Annotated[SavedViews, Depends(get_saved_views)],
) -> list[SavedViewResponse]:
    return [_saved_view(item) for item in use_case.list(actor)]


@saved_view_router.post("", response_model=SavedViewResponse, status_code=201)
def create_saved_view(
    body: SavedViewCreateRequest,
    actor: CurrentActorDep,
    use_case: Annotated[SavedViews, Depends(get_saved_views)],
) -> SavedViewResponse:
    return _saved_view(use_case.create(actor, body.name, _criteria(body.criteria)))


@saved_view_router.put("/{view_id}", response_model=SavedViewResponse)
def update_saved_view(
    view_id: str,
    body: SavedViewUpdateRequest,
    actor: CurrentActorDep,
    use_case: Annotated[SavedViews, Depends(get_saved_views)],
) -> SavedViewResponse:
    return _saved_view(
        use_case.update(actor, view_id, body.name, _criteria(body.criteria), body.expected_version)
    )


@saved_view_router.delete("/{view_id}", status_code=204)
def delete_saved_view(
    view_id: str,
    expected_version: Annotated[int, Query(ge=1)],
    actor: CurrentActorDep,
    use_case: Annotated[SavedViews, Depends(get_saved_views)],
) -> Response:
    use_case.delete(actor, view_id, expected_version)
    return Response(status_code=204)
