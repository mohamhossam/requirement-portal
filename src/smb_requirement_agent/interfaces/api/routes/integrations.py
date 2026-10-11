"""The work-item tracker's service hook (ontology plan Phase 7).

Public, because the tracker signs in with Basic auth and `ADO_HOOK_SECRET` rather than as a
person; `TrackerHook.admits` checks it. Served only when the secret and a knowledge service
are both configured, and 404 otherwise. Every event answers 202 once admitted, so the tracker
does not retry one this portal has nothing to do with; the same event twice is queued once.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from smb_requirement_agent.governance.application.use_cases.delivery_closure import TrackerEvent
from smb_requirement_agent.interfaces.api.dependencies import ContainerDep
from smb_requirement_agent.interfaces.api.schemas.integrations import (
    TrackerEventAnswer,
    TrackerEventBody,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])

UPDATED = "workitem.updated"


@router.post(
    "/azure-devops/work-items",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TrackerEventAnswer,
)
def receive_work_item_event(
    body: TrackerEventBody,
    container: ContainerDep,
    authorization: Annotated[str | None, Header()] = None,
) -> TrackerEventAnswer:
    """Queue a published Epic closed or removed in the tracker; ignore every other event."""
    hook = container.tracker_hook
    if hook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    if not hook.admits(authorization):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The service hook's credentials are not valid.",
            headers={"WWW-Authenticate": 'Basic realm="tracker"'},
        )
    item_id = body.resource.item_id()
    state = body.resource.new_state()
    if body.event_type != UPDATED or item_id is None or state is None:
        return TrackerEventAnswer(status="ignored")
    closure = hook.record.execute(
        TrackerEvent(
            event_id=body.id,
            work_item_id=item_id,
            state=state,
            occurred_at=body.created_date,
        )
    )
    if closure is None:
        return TrackerEventAnswer(status="ignored")
    return TrackerEventAnswer(status="queued", closure_id=closure.closure_id)
