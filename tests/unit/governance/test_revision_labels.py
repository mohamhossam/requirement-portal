"""What each revision changed, in a few words (ADR-0119 Amendment 1)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from smb_requirement_agent.governance.application.use_cases.revision_history import (
    describe_breakdown_revision,
    describe_requirement_revision,
)
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.unit.workflow_helpers import approve_fake_breakdown, post_analysis


def _breakdown_labels(container: Container, requirement_id: str) -> list[str]:
    labels: list[str] = []
    previous = None
    for item in container.breakdown_repository.list_breakdown_revisions(
        RequirementId(requirement_id)
    ):
        labels.append(describe_breakdown_revision(previous, item))
        previous = item
    return labels


def _requirement_labels(container: Container, requirement_id: str) -> list[str]:
    labels: list[str] = []
    previous = None
    for item in container.breakdown_repository.list_requirement_revisions(
        RequirementId(requirement_id)
    ):
        labels.append(describe_requirement_revision(previous, item))
        previous = item
    return labels


def test_breakdown_revisions_are_labelled_by_what_changed(
    client: TestClient, container: Container
) -> None:
    requirement_id, _, _ = approve_fake_breakdown(client)

    labels = _breakdown_labels(container, requirement_id)

    assert labels[0] == "Analysis generated, round 1"
    assert labels[1] == "Analysis re-run, round 2; Clarification answered"
    assert "Business-intent decision recorded" in labels
    assert "Analysis confirmed" in labels
    assert "Epic generated" in labels
    assert any(label.startswith("Features generated (2)") for label in labels)
    assert any("Review generated" in label for label in labels)
    assert any(label.startswith("Stories generated (2)") for label in labels)
    assert "Submitted for review" in labels
    assert labels[-1] == "Final approval recorded"
    # Every revision is a change of some kind; nothing is labelled as a repeat.
    assert "Recorded again" not in labels


def test_requirement_revisions_are_labelled_by_what_changed(
    client: TestClient, container: Container
) -> None:
    requirement_id = client.post(
        "/requirements", json={"title": "Order in one visit", "description": "First wording."}
    ).json()["id"]
    assert post_analysis(client, requirement_id).succeeded
    access = client.get(f"/requirements/{requirement_id}/assignments").json()
    assert (
        client.put(
            f"/requirements/{requirement_id}/reviewers/fake-reviewer",
            json={"expected_version": access["version"]},
        ).status_code
        == 200
    )
    current = client.get(f"/requirements/{requirement_id}").json()
    edited = client.put(
        f"/requirements/{requirement_id}",
        json={
            "title": "Order in one visit, online",
            "description": "First wording.",
            "channels": ["Web"],
            "expected_version": current["version"],
            "impact_acknowledged": True,
        },
    )
    assert edited.status_code == 200, edited.text

    labels = _requirement_labels(container, requirement_id)

    assert labels[0] == "Need captured"
    assert "Team changed" in labels
    assert labels[-1] == "Need edited: title, channels"
