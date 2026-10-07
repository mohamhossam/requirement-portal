"""Slice 5C tests for resumable structured drafts and analysis eligibility."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.errors import RequirementVersionConflictError
from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirement
from smb_requirement_agent.application.use_cases.requirement_drafts import (
    CreateRequirementDraft,
    GetRequirementDraft,
    ListRequirementDrafts,
    PromoteRequirementDraft,
    RequirementDraftInput,
    SaveRequirementDraft,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_document_repository import (
    InMemoryDocumentRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_requirement_draft_repository import (  # noqa: E501
    InMemoryRequirementDraftRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_requirement_repository import (
    InMemoryRequirementRepository,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.unit.transaction_stub import NoOpTransactionManager
from tests.unit.workflow_helpers import post_analysis

NOW = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)


def test_partial_draft_is_saved_resumed_and_reports_missing_fields() -> None:
    drafts = InMemoryRequirementDraftRepository()
    clock = FixedClock(NOW)
    created = CreateRequirementDraft(drafts, clock).execute(
        RequirementDraftInput(title="  New offer  ")
    )

    assert created.title == "New offer"
    assert created.analysis_eligibility.missing_fields == ("description",)
    assert GetRequirementDraft(drafts).execute(created.id) == created
    assert ListRequirementDrafts(drafts).execute() == (created,)


def test_autosave_uses_optimistic_versions_and_normalizes_lists() -> None:
    drafts = InMemoryRequirementDraftRepository()
    clock = FixedClock(NOW)
    created = CreateRequirementDraft(drafts, clock).execute(RequirementDraftInput())
    save = SaveRequirementDraft(drafts, clock)
    data = RequirementDraftInput(
        title="Title",
        description="Need",
        desired_outcome="Outcome",
        channels=(" Web ", ""),
    )

    saved = save.execute(created.id, data, expected_version=1)

    assert saved.version.value == 2
    assert saved.channels == ("Web",)
    assert saved.analysis_eligibility.eligible
    with pytest.raises(RequirementVersionConflictError):
        save.execute(created.id, data, expected_version=1)


def test_promoting_a_draft_preserves_structured_context_and_removes_draft() -> None:
    drafts = InMemoryRequirementDraftRepository()
    requirements = InMemoryRequirementRepository()
    draft = CreateRequirementDraft(drafts, FixedClock(NOW)).execute(
        RequirementDraftInput(
            title="Title",
            description="Need",
            desired_outcome="Outcome",
            customer_context="SMB customers",
            systems=("Ordering",),
            business_rules=("Explicit rule",),
        )
    )

    requirement = PromoteRequirementDraft(
        drafts,
        InMemoryDocumentRepository(),
        CreateRequirement(requirements),
        NoOpTransactionManager(),
    ).execute(draft.id, draft.version.value)

    assert requirement.desired_outcome is not None
    assert requirement.desired_outcome.value == "Outcome"
    assert requirement.customer_context is not None
    assert requirement.customer_context.value == "SMB customers"
    assert [item.value for item in requirement.systems] == ["Ordering"]
    assert drafts.get(draft.id) is None


def test_draft_api_supports_partial_save_resume_and_conflict(client: TestClient) -> None:
    created = client.post("/requirements/drafts", json={})
    assert created.status_code == 201
    draft = created.json()
    assert draft["analysis_eligibility"]["eligible"] is False

    body = {
        "title": "Title",
        "description": "Need",
        "desired_outcome": "Outcome",
        "channels": ["Web"],
        "expected_version": draft["version"],
    }
    saved = client.put(f"/requirements/drafts/{draft['id']}", json=body)
    assert saved.status_code == 200
    assert saved.json()["version"] == 2
    assert saved.json()["analysis_eligibility"]["eligible"] is True
    assert client.get(f"/requirements/drafts/{draft['id']}").json() == saved.json()

    conflict = client.put(f"/requirements/drafts/{draft['id']}", json=body)
    assert conflict.status_code == 409


def test_analysis_can_start_when_promoted_source_has_no_desired_outcome(
    client: TestClient,
) -> None:
    draft = client.post(
        "/requirements/drafts", json={"title": "Title", "description": "Need"}
    ).json()
    requirement = client.post(
        f"/requirements/drafts/{draft['id']}/promote",
        json={"expected_version": draft["version"]},
    )
    assert requirement.status_code == 201
    requirement_id = requirement.json()["id"]
    assert requirement.json()["analysis_eligibility"] == {
        "eligible": True,
        "missing_fields": [],
    }
    analysis = post_analysis(client, requirement_id)
    assert analysis.status_code == 200
    assert analysis.json()["business_intent"]["proposals"][0]["kind"] == "desired_outcome"


def test_unknown_draft_returns_centralized_not_found(client: TestClient) -> None:
    response = client.get(f"/requirements/drafts/{RequirementId('missing').value}")
    assert response.status_code == 404
