"""Bounds on Requirement source content and on request bodies."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.domain.requirement.entities import Requirement, RequirementDraft
from smb_requirement_agent.domain.requirement.errors import RequirementIntakeTooLargeError
from smb_requirement_agent.domain.requirement.intake_limits import (
    MAX_DESCRIPTION_CHARACTERS,
    MAX_LIST_ITEM_CHARACTERS,
    MAX_LIST_ITEMS,
    MAX_TITLE_CHARACTERS,
    require_within_intake_limits,
)
from smb_requirement_agent.domain.requirement.value_objects import (
    RequirementContext,
    RequirementDescription,
    RequirementId,
    RequirementStatus,
    RequirementTitle,
    RequirementVersion,
)
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from tests.conftest import FAKE_PROVIDER_SETTINGS

NOW = datetime(2026, 9, 24, tzinfo=UTC)


def _within(
    *,
    title: str = "T",
    description: str = "D",
    customer_context: str | None = None,
    lists: Mapping[str, Sequence[str]] | None = None,
) -> None:
    require_within_intake_limits(
        title=title,
        description=description,
        desired_outcome=None,
        customer_context=customer_context,
        lists=lists or {},
    )


class TestLimits:
    def test_content_at_the_limits_is_accepted(self) -> None:
        _within(
            title="t" * MAX_TITLE_CHARACTERS,
            description="d" * MAX_DESCRIPTION_CHARACTERS,
            lists={"channels": ["c" * MAX_LIST_ITEM_CHARACTERS] * MAX_LIST_ITEMS},
        )

    @pytest.mark.parametrize(
        ("overrides", "field"),
        [
            ({"title": "t" * (MAX_TITLE_CHARACTERS + 1)}, "title"),
            ({"description": "d" * (MAX_DESCRIPTION_CHARACTERS + 1)}, "description"),
            ({"customer_context": "c" * 10_001}, "customer_context"),
            ({"lists": {"systems": ["s"] * (MAX_LIST_ITEMS + 1)}}, "systems"),
            ({"lists": {"channels": ["c" * (MAX_LIST_ITEM_CHARACTERS + 1)]}}, "channels"),
        ],
    )
    def test_the_first_field_over_its_limit_is_named(
        self, overrides: dict[str, Any], field: str
    ) -> None:
        with pytest.raises(RequirementIntakeTooLargeError, match=field):
            _within(**overrides)

    def test_surrounding_whitespace_does_not_count(self) -> None:
        _within(title="  " + "t" * MAX_TITLE_CHARACTERS + "  ")


def _requirement() -> Requirement:
    return Requirement(
        id=RequirementId("req-1"),
        title=RequirementTitle("T"),
        description=RequirementDescription("D"),
        status=RequirementStatus.DRAFT,
        version=RequirementVersion(1),
    )


def test_editing_a_requirement_applies_the_limits() -> None:
    with pytest.raises(RequirementIntakeTooLargeError, match="title"):
        _requirement().update(
            RequirementTitle("t" * (MAX_TITLE_CHARACTERS + 1)), RequirementDescription("D")
        )


def test_revising_a_draft_applies_the_limits() -> None:
    draft = RequirementDraft(
        RequirementId("draft-1"), "", "", "", "", (), (), (), (), RequirementVersion(1), NOW
    )

    with pytest.raises(RequirementIntakeTooLargeError, match="business_rules"):
        draft.revise(
            title="T",
            description="D",
            desired_outcome="",
            customer_context="",
            channels=(),
            systems=(),
            business_rules=("r",) * (MAX_LIST_ITEMS + 1),
            constraints=(),
            updated_at=NOW,
        )


def test_records_stored_before_the_limits_still_load() -> None:
    # Reconstitution builds value objects directly and must not start failing.
    legacy = replace(
        _requirement(),
        title=RequirementTitle("t" * (MAX_TITLE_CHARACTERS * 2)),
        channels=(RequirementContext("c" * (MAX_LIST_ITEM_CHARACTERS * 2)),),
    )

    assert len(legacy.title.value) == MAX_TITLE_CHARACTERS * 2


class TestApi:
    def test_an_over_long_title_is_refused_at_the_boundary(self, client: TestClient) -> None:
        response = client.post(
            "/requirements",
            json={"title": "t" * (MAX_TITLE_CHARACTERS + 1), "description": "D"},
        )

        assert response.status_code == 422
        assert "title" in response.json()["message"]

    def test_a_body_over_the_ceiling_is_refused_with_413(self) -> None:
        container = build_container(replace(FAKE_PROVIDER_SETTINGS, request_max_body_bytes=4096))
        with TestClient(create_app(lambda: container)) as client:
            response = client.post(
                "/requirements",
                json={"title": "T", "description": "d" * 8000},
                headers={"X-Request-ID": "big-1"},
            )

        assert response.status_code == 413
        assert response.json()["code"] == "request_body_too_large"
        assert response.json()["correlation_id"] == "big-1"

    def test_a_streamed_body_without_a_length_is_counted(self) -> None:
        container = build_container(replace(FAKE_PROVIDER_SETTINGS, request_max_body_bytes=4096))

        def chunks() -> Iterator[bytes]:
            yield b'{"title": "T", "description": "'
            for _ in range(10):
                yield b"d" * 1000
            yield b'"}'

        with TestClient(create_app(lambda: container)) as client:
            response = client.post(
                "/requirements",
                content=chunks(),
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 413

    def test_uploads_may_carry_a_file_beyond_the_json_ceiling(self) -> None:
        settings = replace(
            FAKE_PROVIDER_SETTINGS, request_max_body_bytes=4096, document_max_file_bytes=64_000
        )
        container = build_container(settings)
        with TestClient(create_app(lambda: container)) as client:
            created = client.post("/requirements", json={"title": "T", "description": "D"})
            response = client.post(
                f"/requirements/{created.json()['id']}/attachments",
                files={"file": ("notes.txt", b"x" * 20_000, "text/plain")},
            )
            too_big = client.post(
                f"/requirements/{created.json()['id']}/attachments",
                files={"file": ("notes.txt", b"x" * 80_000, "text/plain")},
            )

        assert response.status_code in (200, 201)
        assert too_big.status_code == 413
