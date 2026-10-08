"""RequirementCommands owns the order of a Requirement-scoped unit of work."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar, cast

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementPermission,
)
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.workflows.application.use_cases.generation_context import (
    GenerationContextTokens,
)
from smb_requirement_agent.workflows.application.use_cases.identity_access import (
    RequirementAccessService,
)
from smb_requirement_agent.workflows.application.use_cases.requirement_commands import (
    ExpectedContext,
    RequirementCommands,
)

T = TypeVar("T")
REQUIREMENT = RequirementId("requirement-1")
ACTOR = ActorProfile(ActorId("fake-owner"), "Amina Owner")


class RecordingAccess:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    @contextmanager
    def mutation(
        self,
        requirement_id: RequirementId,
        current: ActorProfile,
        permission: RequirementPermission,
    ) -> Iterator[None]:
        self.events.append(f"{permission.value} fence")
        yield


class RecordingContexts:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    @contextmanager
    def read_snapshot(self, requirement_id: RequirementId) -> Iterator[None]:
        self.events.append("snapshot open")
        yield
        self.events.append("snapshot closed")

    @staticmethod
    def require(displayed: str, current: str) -> None:
        GenerationContextTokens.require(displayed, current)


def _commands(events: list[str]) -> RequirementCommands:
    return RequirementCommands(
        cast(RequirementAccessService, RecordingAccess(events)),
        cast(GenerationContextTokens, RecordingContexts(events)),
    )


def _command(events: list[str], result: str = "result") -> Callable[[], str]:
    def run() -> str:
        events.append("command")
        return result

    return run


def test_run_fences_then_checks_context_then_runs_the_command() -> None:
    events: list[str] = []

    def current_context() -> str:
        events.append("context read")
        return "token"

    expected = ExpectedContext("token", current_context)

    result = _commands(events).run(REQUIREMENT, ACTOR, _command(events), expected=expected)

    assert result == "result"
    assert events == ["member fence", "context read", "command"]


def test_stale_context_rejects_before_the_command_runs() -> None:
    events: list[str] = []

    with pytest.raises(ArtifactVersionConflictError):
        _commands(events).run(
            REQUIREMENT,
            ACTOR,
            _command(events),
            expected=ExpectedContext("shown-earlier", lambda: "current"),
        )

    assert "command" not in events


def test_commands_apply_the_member_baseline_and_leave_stricter_rules_to_use_cases() -> None:
    # Delivery code cannot choose a permission: every command gets the member
    # fence, and a use case that needs the owner enforces it itself.
    events: list[str] = []

    _commands(events).run(REQUIREMENT, ACTOR, _command(events))

    assert events == ["member fence", "command"]


def test_view_is_built_inside_the_same_snapshot_as_the_command() -> None:
    events: list[str] = []

    def present(result: str) -> str:
        events.append(f"present {result}")
        return result.upper()

    view = _commands(events).run_and_present(REQUIREMENT, ACTOR, _command(events), present)

    assert view == "RESULT"
    assert events == [
        "snapshot open",
        "member fence",
        "command",
        "present result",
        "snapshot closed",
    ]


def test_read_happens_inside_a_snapshot() -> None:
    events: list[str] = []

    def read() -> str:
        events.append("read")
        return "view"

    assert _commands(events).read(REQUIREMENT, read) == "view"
    assert events == ["snapshot open", "read", "snapshot closed"]


OWNER = {"X-Fake-Actor-Id": "fake-owner"}
OUTSIDER = {"X-Fake-Actor-Id": "fake-reviewer"}


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        # Route wrappers were removed: these use cases fence themselves.
        ("post", "/requirements/{id}/breakdown-review", None),
        ("post", "/requirements/{id}/architecture-mapping", None),
        (
            "put",
            "/requirements/{id}/attachments/missing/analysis-inclusion",
            {"included": True, "expected_version": 1},
        ),
        # Converted to RequirementCommands.
        ("post", "/requirements/{id}/analysis", {"context_token": "any", "force": False}),
        ("post", "/requirements/{id}/epic", {"context_token": "any", "force": False}),
        (
            "put",
            "/requirements/{id}",
            {
                "title": "Changed",
                "description": "Changed",
                "expected_version": 1,
                "impact_acknowledged": True,
            },
        ),
    ],
)
def test_non_members_are_still_refused_after_route_fences_moved(
    client: TestClient, method: str, path: str, payload: dict[str, Any] | None
) -> None:
    created = client.post(
        "/requirements",
        json={"title": "Bulk SIM activation", "description": "Activate many SIMs at once."},
        headers=OWNER,
    )
    assert created.status_code == 201, created.text
    url = path.format(id=created.json()["id"])

    response = client.request(method, url, json=payload, headers=OUTSIDER)

    assert response.status_code == 403, response.text
