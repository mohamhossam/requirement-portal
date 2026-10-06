"""Durable AI job and actor-notification routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response

from smb_requirement_agent.application.ports.ai_jobs import AiJobCommand, JsonValue
from smb_requirement_agent.application.use_cases.ai_jobs import (
    DEFAULT_LIST_LIMIT,
    MAX_LIST_LIMIT,
    AiJobs,
    Notifications,
)
from smb_requirement_agent.domain.jobs.entities import (
    ActorNotification,
    AiJob,
    AiJobId,
    AiJobOperation,
    NotificationId,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    get_ai_jobs,
    get_notifications,
    limit_provider_calls,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.routes.identity import actor_response
from smb_requirement_agent.interfaces.api.schemas.jobs import (
    AiJobFailureResponse,
    AiJobResponse,
    AiJobResultResourceResponse,
    AiJobStartRequest,
    CancelAiJobRequest,
    NotificationPreferenceRequest,
    NotificationPreferenceResponse,
    NotificationResponse,
    RetryAiJobRequest,
)

router = APIRouter(
    prefix="/requirements",
    tags=["ai-jobs"],
    dependencies=[Depends(require_authenticated_actor)],
)
notification_router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_authenticated_actor)],
)


def job_response(job: AiJob, command: AiJobCommand | None = None) -> AiJobResponse:
    item_count = None
    if job.operation is AiJobOperation.RESOLVE_CLARIFICATION_QUESTIONS and command is not None:
        answers = command.arguments.get("answers")
        if isinstance(answers, list):
            item_count = len(answers)
    return AiJobResponse(
        id=job.id.value,
        version=job.version,
        requirement_id=job.requirement_id.value,
        operation=job.operation,
        status=job.status,
        created_by=actor_response(job.created_by),
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        cancel_requested_at=job.cancel_requested_at,
        attempt_count=job.attempt_count,
        retry_of_job_id=job.retry_of_job_id.value if job.retry_of_job_id else None,
        failure=(
            AiJobFailureResponse(
                code=job.failure.code,
                message=job.failure.message,
                retryable=job.failure.retryable,
                correlation_id=job.failure.correlation_id,
            )
            if job.failure
            else None
        ),
        result_resources=[
            AiJobResultResourceResponse(kind=item.kind, path=item.path)
            for item in job.result_resources
        ],
        item_count=item_count,
        origin=job.origin,
        phase=job.phase,
        completed_units=job.completed_units,
        total_units=job.total_units,
        current_section_label=job.current_section_label,
    )


def notification_response(notification: ActorNotification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id.value,
        job_id=notification.job_id.value if notification.job_id is not None else None,
        kind=notification.kind,
        message=notification.message,
        created_at=notification.created_at,
        resource_path=notification.resource_path,
        read_at=notification.read_at,
    )


def _command(body: AiJobStartRequest) -> AiJobCommand:
    data = body.model_dump(mode="json", exclude={"operation"})
    return AiJobCommand({key: _json_value(value) for key, value in data.items()})


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    raise TypeError(f"Unsupported AI job command value {type(value).__name__}.")


@router.post(
    "/{requirement_id}/ai-jobs",
    response_model=AiJobResponse,
    status_code=202,
    dependencies=[Depends(limit_provider_calls)],
)
def start_ai_job(
    requirement_id: str,
    body: AiJobStartRequest,
    response: Response,
    actor: CurrentActorDep,
    use_case: Annotated[AiJobs, Depends(get_ai_jobs)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> AiJobResponse:
    command = _command(body)
    result = use_case.start(
        RequirementId(requirement_id),
        body.operation,
        command,
        idempotency_key,
        actor,
    )
    if not result.created and result.job.status.terminal:
        response.status_code = 200
    return job_response(result.job, command)


@router.get("/{requirement_id}/ai-jobs", response_model=list[AiJobResponse])
def list_ai_jobs(
    requirement_id: str,
    use_case: Annotated[AiJobs, Depends(get_ai_jobs)],
    active_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=MAX_LIST_LIMIT)] = DEFAULT_LIST_LIMIT,
) -> list[AiJobResponse]:
    return [
        job_response(record.job, record.command)
        for record in use_case.list(
            RequirementId(requirement_id), active_only=active_only, limit=limit
        )
    ]


@router.get("/{requirement_id}/ai-jobs/{job_id}", response_model=AiJobResponse)
def get_ai_job(
    requirement_id: str,
    job_id: str,
    use_case: Annotated[AiJobs, Depends(get_ai_jobs)],
) -> AiJobResponse:
    resolved_requirement_id = RequirementId(requirement_id)
    resolved_job_id = AiJobId(job_id)
    return job_response(
        use_case.get(resolved_requirement_id, resolved_job_id),
        use_case.command(resolved_requirement_id, resolved_job_id),
    )


@router.post("/{requirement_id}/ai-jobs/{job_id}/cancellation", response_model=AiJobResponse)
def cancel_ai_job(
    requirement_id: str,
    job_id: str,
    actor: CurrentActorDep,
    body: CancelAiJobRequest,
    use_case: Annotated[AiJobs, Depends(get_ai_jobs)],
) -> AiJobResponse:
    resolved_requirement_id = RequirementId(requirement_id)
    resolved_job_id = AiJobId(job_id)
    return job_response(
        use_case.cancel(
            resolved_requirement_id,
            resolved_job_id,
            actor,
            expected_version=body.expected_version,
        ),
        use_case.command(resolved_requirement_id, resolved_job_id),
    )


@router.post(
    "/{requirement_id}/ai-jobs/{job_id}/retry",
    response_model=AiJobResponse,
    status_code=202,
    dependencies=[Depends(limit_provider_calls)],
)
def retry_ai_job(
    requirement_id: str,
    job_id: str,
    actor: CurrentActorDep,
    body: RetryAiJobRequest,
    use_case: Annotated[AiJobs, Depends(get_ai_jobs)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> AiJobResponse:
    result = use_case.retry(
        RequirementId(requirement_id),
        AiJobId(job_id),
        idempotency_key,
        actor,
        expected_version=body.expected_version,
    )
    return job_response(
        result.job,
        use_case.command(RequirementId(requirement_id), result.job.id),
    )


@notification_router.get("", response_model=list[NotificationResponse])
def list_notifications(
    actor: CurrentActorDep,
    use_case: Annotated[Notifications, Depends(get_notifications)],
    unread_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=MAX_LIST_LIMIT)] = DEFAULT_LIST_LIMIT,
) -> list[NotificationResponse]:
    return [
        notification_response(item)
        for item in use_case.list(actor.id, unread_only=unread_only, limit=limit)
    ]


@notification_router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[Notifications, Depends(get_notifications)],
) -> NotificationResponse:
    return notification_response(use_case.mark_read(NotificationId(notification_id), actor.id))


@notification_router.get("/preferences/current", response_model=NotificationPreferenceResponse)
def get_notification_preference(
    actor: CurrentActorDep,
    use_case: Annotated[Notifications, Depends(get_notifications)],
) -> NotificationPreferenceResponse:
    return NotificationPreferenceResponse(
        browser_enabled=use_case.preference(actor.id).browser_enabled
    )


@notification_router.put("/preferences/current", response_model=NotificationPreferenceResponse)
def set_notification_preference(
    body: NotificationPreferenceRequest,
    actor: CurrentActorDep,
    use_case: Annotated[Notifications, Depends(get_notifications)],
) -> NotificationPreferenceResponse:
    return NotificationPreferenceResponse(
        browser_enabled=use_case.set_preference(actor.id, body.browser_enabled).browser_enabled
    )
