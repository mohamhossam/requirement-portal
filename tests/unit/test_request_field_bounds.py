"""Over-long request fields are refused as 422 before any use case runs.

`tests/architecture/test_request_bounds.py` proves every field declares a
maximum; these prove the maximum is enforced, and that a value at the maximum
still reaches the use case (here a 404, because the Requirement is absent).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.interfaces.api.schemas.bounds import (
    MAX_IDENTIFIER_CHARACTERS,
    MAX_ITEMS,
    MAX_TEXT_CHARACTERS,
)
from tests.conftest import FAKE_PROVIDER_SETTINGS

OWNER = {"X-Fake-Actor-Id": "fake-owner"}
MISSING = "/requirements/no-such-requirement"


@pytest.fixture
def api() -> Iterator[TestClient]:
    container = build_container(FAKE_PROVIDER_SETTINGS)
    with TestClient(create_app(lambda: container)) as client:
        yield client


def _answers(count: int) -> list[dict[str, Any]]:
    return [
        {"question_id": f"q-{index}", "answer": "Yes.", "expected_version": 1}
        for index in range(count)
    ]


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        pytest.param(
            "put",
            f"{MISSING}/analysis/questions/q/draft",
            {"answer": "a" * (MAX_TEXT_CHARACTERS + 1), "expected_version": 1},
            id="draft answer",
        ),
        pytest.param(
            "post",
            f"{MISSING}/breakdown-review/comments",
            {
                "target_kind": "epic",
                "target_id": "epic-1",
                "body": "b" * (MAX_TEXT_CHARACTERS + 1),
                "expected_version": 1,
            },
            id="review comment",
        ),
        pytest.param(
            "post",
            f"{MISSING}/ai-jobs",
            {
                "operation": "resolve_clarification_question",
                "question_id": "q" * (MAX_IDENTIFIER_CHARACTERS + 1),
                "expected_version": 1,
            },
            id="job identifier",
        ),
        pytest.param(
            "post",
            f"{MISSING}/analysis/question-resolutions",
            {"answers": _answers(MAX_ITEMS + 1)},
            id="answer batch",
        ),
    ],
)
def test_an_over_long_field_is_refused_before_the_use_case(
    api: TestClient, method: str, path: str, body: dict[str, Any]
) -> None:
    response = api.request(method.upper(), path, json=body, headers=OWNER)

    assert response.status_code == 422


def test_a_field_at_its_maximum_reaches_the_use_case(api: TestClient) -> None:
    response = api.put(
        f"{MISSING}/analysis/questions/q/draft",
        json={"answer": "a" * MAX_TEXT_CHARACTERS, "expected_version": 1},
        headers=OWNER,
    )

    assert response.status_code == 404
