"""What the work-item tracker's service hook sends (ontology plan Phase 7).

Azure DevOps posts a `workitem.updated` event: its own id, when it was raised, and the
resource, which names the work item and carries only the fields this update changed. Every
other field is read leniently, since the tracker adds fields over time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from smb_requirement_agent.interfaces.api.schemas.bounds import Identifier, Name


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class FieldChange(_Lenient):
    old_value: Name | None = Field(default=None, alias="oldValue")
    new_value: Name | None = Field(default=None, alias="newValue")


class ChangedFields(_Lenient):
    # Only the state is read; the tracker's other fields are left unparsed.
    state: FieldChange | None = Field(default=None, alias="System.State")


class WorkItemRevision(_Lenient):
    id: int | None = None


class WorkItemUpdate(_Lenient):
    # On an update, `id` is the update's own number and `workItemId` the work item's.
    work_item_id: int | None = Field(default=None, alias="workItemId")
    fields: ChangedFields = Field(default_factory=ChangedFields)
    revision: WorkItemRevision | None = None

    def item_id(self) -> str | None:
        found = self.work_item_id or (self.revision.id if self.revision is not None else None)
        return str(found) if found else None

    def new_state(self) -> str | None:
        """The state this update moved the work item to, or None when it left it alone."""
        change = self.fields.state
        return change.new_value or None if change is not None else None


class TrackerEventBody(_Lenient):
    id: str = Field(min_length=1, max_length=200)
    event_type: Identifier = Field(alias="eventType")
    created_date: datetime = Field(alias="createdDate")
    resource: WorkItemUpdate


class TrackerEventAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    # queued: a closed or removed Epic this portal published; ignored: anything else.
    status: Literal["queued", "ignored"]
    closure_id: str | None = None
