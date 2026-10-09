from __future__ import annotations

from datetime import UTC, datetime

import pytest
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.reporting.application.errors import (
    InvalidSavedViewError,
    SavedViewConflictError,
    SavedViewNotFoundError,
)
from smb_requirement_agent.reporting.application.ports.requirement_worklist import (
    WorkflowStatus,
    WorklistSort,
)
from smb_requirement_agent.reporting.application.ports.saved_views import SavedViewCriteria
from smb_requirement_agent.reporting.application.use_cases.saved_views import SavedViews
from smb_requirement_agent.reporting.infrastructure.in_memory_saved_views import (
    InMemorySavedViewRepository,
)
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
)

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)
OWNER = ActorProfile(ActorId("owner"), "Owner")
OTHER = ActorProfile(ActorId("other"), "Other")


def test_saved_view_crud_round_trips_only_worklist_criteria() -> None:
    views = SavedViews(InMemorySavedViewRepository(), FixedClock(NOW))
    criteria = SavedViewCriteria(
        "  fibre  ",
        (WorkflowStatus.NEEDS_ANSWERS, WorkflowStatus.NEEDS_ANSWERS),
        WorklistSort.TITLE_ASC,
        ActorId("owner"),
        True,
    )

    created = views.create(OWNER, " My queue ", criteria)

    assert created.name == "My queue"
    assert created.criteria.query == "fibre"
    assert created.criteria.workflow_statuses == (WorkflowStatus.NEEDS_ANSWERS,)
    assert views.list(OWNER) == (created,)
    updated = views.update(
        OWNER,
        created.id,
        "Renamed",
        SavedViewCriteria(sort=WorklistSort.UPDATED_ASC),
        expected_version=1,
    )
    assert updated.version == 2
    assert updated.criteria.sort is WorklistSort.UPDATED_ASC
    views.delete(OWNER, created.id, expected_version=2)
    assert views.list(OWNER) == ()


def test_saved_view_names_are_unique_per_actor_and_actor_isolation_is_404() -> None:
    views = SavedViews(InMemorySavedViewRepository(), FixedClock(NOW))
    created = views.create(OWNER, "Priority", SavedViewCriteria())
    views.create(OTHER, "priority", SavedViewCriteria())

    with pytest.raises(SavedViewConflictError):
        views.create(OWNER, " PRIORITY ", SavedViewCriteria())
    with pytest.raises(SavedViewNotFoundError):
        views.update(OTHER, created.id, "Stolen", SavedViewCriteria(), 1)
    with pytest.raises(SavedViewNotFoundError):
        views.delete(OTHER, created.id, 1)


def test_saved_view_rejects_stale_versions_and_blank_names() -> None:
    views = SavedViews(InMemorySavedViewRepository(), FixedClock(NOW))
    created = views.create(OWNER, "Priority", SavedViewCriteria())

    with pytest.raises(SavedViewConflictError):
        views.update(OWNER, created.id, "Priority", SavedViewCriteria(), 99)
    with pytest.raises(SavedViewConflictError):
        views.delete(OWNER, created.id, 99)
    with pytest.raises(InvalidSavedViewError):
        views.create(OWNER, "   ", SavedViewCriteria())
