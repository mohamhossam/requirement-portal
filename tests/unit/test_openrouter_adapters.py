"""OpenRouter transport and adapter contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from smb_requirement_agent.application.errors import (
    EpicGenerationError,
    KnowledgeGenerationError,
)
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.analysis.value_objects import KnownFact
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementId,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.infrastructure.diagnostics import JsonLinesDebugTrace
from smb_requirement_agent.infrastructure.llm.openrouter_adapters import OpenRouterEpicGenerator
from smb_requirement_agent.infrastructure.llm.openrouter_structured_output import (
    OpenRouterError,
    OpenRouterStructuredOutputClient,
)
from smb_requirement_agent.infrastructure.llm.requirement_knowledge_adapters import (
    OpenRouterKnowledgeEmbedding,
)
from smb_requirement_agent.infrastructure.llm.schemas.epic_schema import EpicSchema
from smb_requirement_agent.infrastructure.llm.structured_output import truncated


def _client(*, trace: JsonLinesDebugTrace | None = None) -> OpenRouterStructuredOutputClient:
    return OpenRouterStructuredOutputClient(
        base_url="https://router.example.test/api/v1",
        http_client=httpx.Client(),
        api_key="sk-or-private",
        model="google/gemma-4-31b-it:free",
        timeout_seconds=120,
        max_output_tokens=8192,
        data_collection="deny",
        debug_trace=trace,
    )


def _response(
    payload: object,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    response.text = json.dumps(payload)
    response.json.return_value = payload
    return response


def _events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_openrouter_client_sends_authenticated_privacy_first_json_mode_with_images() -> None:
    completion = json.dumps(
        {
            "name": "SMB Bundle Offer",
            "outcome": "Bundles can be ordered",
            "business_case": "Supports the stated offer",
        }
    )
    response = _response(
        {"choices": [{"finish_reason": "stop", "message": {"content": completion}}]}
    )

    with patch(
        "smb_requirement_agent.infrastructure.llm.openrouter_structured_output.httpx.Client.post",
        return_value=response,
    ) as post:
        result = _client().parse(
            system_prompt="System rules",
            user_prompt="Requirement text",
            schema_type=EpicSchema,
            images=(("image/png", b"image-bytes"),),
        )

    assert result.name == "SMB Bundle Offer"
    assert post.call_args.args[0] == "https://router.example.test/api/v1/chat/completions"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer sk-or-private"
    body = post.call_args.kwargs["json"]
    assert body["model"] == "google/gemma-4-31b-it:free"
    assert body["response_format"] == {"type": "json_object"}
    assert body["provider"] == {"require_parameters": True, "data_collection": "deny"}
    assert body["max_tokens"] == 8192
    assert "JSON Schema" in body["messages"][0]["content"]
    assert '"business_case"' in body["messages"][0]["content"]
    image_url = body["messages"][1]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")
    assert "reasoning" not in body


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "invalid response object"),
        ({}, "no choices"),
        ({"choices": [None]}, "invalid choice"),
        (
            {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
            "truncated",
        ),
        ({"choices": [{"message": None}]}, "no assistant message"),
        ({"choices": [{"message": {"refusal": "No"}}]}, "refused"),
        ({"choices": [{"message": {"content": " "}}]}, "empty completion"),
        ({"choices": [{"message": {"content": "not-json"}}]}, "did not match"),
        ({"choices": [{"message": {"content": "{}"}}]}, "did not match"),
    ],
)
def test_openrouter_client_rejects_unusable_responses(payload: object, message: str) -> None:
    with (
        patch(
            "smb_requirement_agent.infrastructure.llm.openrouter_structured_output."
            "httpx.Client.post",
            return_value=_response(payload),
        ),
        pytest.raises(OpenRouterError, match=message) as raised,
    ):
        _client().parse(
            system_prompt="System rules",
            user_prompt="Requirement text",
            schema_type=EpicSchema,
        )
    # Only a cut-off answer is marked as one, so a reader can ask for less (ADR-0091).
    assert truncated(raised.value) is (message == "truncated")


@pytest.mark.parametrize("status_code", [401, 500, 503])
def test_openrouter_client_maps_http_failures(status_code: int) -> None:
    request = httpx.Request("POST", "https://router.example.test/api/v1/chat/completions")
    failed = httpx.Response(status_code, request=request)
    response = _response({}, status_code=status_code)
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "rate limited", request=request, response=failed
    )

    with (
        patch(
            "smb_requirement_agent.infrastructure.llm.openrouter_structured_output."
            "httpx.Client.post",
            return_value=response,
        ),
        patch("smb_requirement_agent.infrastructure.llm.openrouter_structured_output.time.sleep"),
        pytest.raises(OpenRouterError, match="request failed"),
    ):
        _client().parse(
            system_prompt="System rules",
            user_prompt="Requirement text",
            schema_type=EpicSchema,
        )


def test_openrouter_client_retries_short_rate_limit_then_succeeds() -> None:
    rate_limited = _response({}, status_code=429, headers={"Retry-After": "2"})
    completion = json.dumps(
        {"name": "Offer", "outcome": "Outcome", "business_case": "Business case"}
    )
    succeeded = _response({"choices": [{"message": {"content": completion}}]})

    with (
        patch(
            "smb_requirement_agent.infrastructure.llm.openrouter_structured_output."
            "httpx.Client.post",
            side_effect=[rate_limited, succeeded],
        ) as post,
        patch(
            "smb_requirement_agent.infrastructure.llm.openrouter_structured_output.time.sleep"
        ) as sleep,
    ):
        result = _client().parse(
            system_prompt="System rules",
            user_prompt="Requirement text",
            schema_type=EpicSchema,
        )

    assert result.name == "Offer"
    assert post.call_count == 2
    sleep.assert_called_once_with(2.0)


def test_openrouter_client_reports_long_rate_limit_without_waiting() -> None:
    request = httpx.Request("POST", "https://router.example.test/api/v1/chat/completions")
    failed = httpx.Response(
        429,
        headers={"Retry-After": "120"},
        request=request,
    )
    response = _response({}, status_code=429, headers={"Retry-After": "120"})
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "rate limited", request=request, response=failed
    )

    with (
        patch(
            "smb_requirement_agent.infrastructure.llm.openrouter_structured_output."
            "httpx.Client.post",
            return_value=response,
        ) as post,
        patch(
            "smb_requirement_agent.infrastructure.llm.openrouter_structured_output.time.sleep"
        ) as sleep,
        pytest.raises(OpenRouterError, match="Retry after 120 seconds"),
    ):
        _client().parse(
            system_prompt="System rules",
            user_prompt="Requirement text",
            schema_type=EpicSchema,
        )

    post.assert_called_once()
    sleep.assert_not_called()


def test_openrouter_client_does_not_multiply_rate_limit_without_retry_after() -> None:
    request = httpx.Request("POST", "https://router.example.test/api/v1/chat/completions")
    failed = httpx.Response(429, request=request)
    response = _response({}, status_code=429)
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "rate limited", request=request, response=failed
    )

    with (
        patch(
            "smb_requirement_agent.infrastructure.llm.openrouter_structured_output."
            "httpx.Client.post",
            return_value=response,
        ) as post,
        patch(
            "smb_requirement_agent.infrastructure.llm.openrouter_structured_output.time.sleep"
        ) as sleep,
        pytest.raises(OpenRouterError, match="Retry later"),
    ):
        _client().parse(
            system_prompt="System rules",
            user_prompt="Requirement text",
            schema_type=EpicSchema,
        )

    post.assert_called_once()
    sleep.assert_not_called()


def test_openrouter_client_rejects_non_json_http_response() -> None:
    response = _response({})
    response.json.side_effect = ValueError("not json")

    with (
        patch(
            "smb_requirement_agent.infrastructure.llm.openrouter_structured_output."
            "httpx.Client.post",
            return_value=response,
        ),
        pytest.raises(OpenRouterError, match="non-JSON"),
    ):
        _client().parse(
            system_prompt="System rules",
            user_prompt="Requirement text",
            schema_type=EpicSchema,
        )


def test_openrouter_trace_redacts_authorization_and_image_bytes(tmp_path: Path) -> None:
    path = tmp_path / "debug.log"
    trace = JsonLinesDebugTrace(str(path))
    completion = json.dumps(
        {"name": "Offer", "outcome": "Outcome", "business_case": "Business case"}
    )
    response = _response({"choices": [{"message": {"content": completion}}]})

    with patch(
        "smb_requirement_agent.infrastructure.llm.openrouter_structured_output.httpx.Client.post",
        return_value=response,
    ):
        _client(trace=trace).parse(
            system_prompt="System rules",
            user_prompt="Requirement text",
            schema_type=EpicSchema,
            images=(("image/png", b"image-bytes"),),
        )
    trace.record("secret.check", openrouter_api_key="sk-or-private")
    trace.close()

    events = _events(path)
    request_body = next(
        item["details"]["request_body"] for item in events if item["event"] == "openrouter.request"
    )
    assert request_body["messages"][1]["content"][1]["image_url"]["url"] == (
        "[REDACTED: image/png data URL]"
    )
    secret = next(item for item in events if item["event"] == "secret.check")
    assert secret["details"]["openrouter_api_key"] == "[REDACTED]"
    assert "sk-or-private" not in path.read_text(encoding="utf-8")


def test_openrouter_epic_adapter_preserves_model_provenance() -> None:
    parsed = EpicSchema(name="Offer", outcome="Outcome", business_case="Business case")
    client = MagicMock()
    client.model = "google/gemma-4-31b-it:free"
    client.parse.return_value = parsed
    requirement = Requirement(
        RequirementId("requirement-1"),
        RequirementTitle("Bundle"),
        RequirementDescription("Make the bundle orderable."),
        RequirementStatus.DRAFT,
    )
    analysis = RequirementAnalysis(
        requirement_id=requirement.id,
        known_facts=(KnownFact("The bundle must be orderable."),),
        constraints=(),
        business_rules=(),
        assumptions=(),
        open_questions=(),
        ambiguities=(),
        potential_dependencies=(),
    )

    with patch(
        "smb_requirement_agent.infrastructure.llm.openrouter_adapters._client_from_settings",
        return_value=client,
    ):
        adapter = OpenRouterEpicGenerator(
            base_url="https://router.example.test/api/v1",
            http_client=httpx.Client(),
            api_key="sk-or-private",
            model="google/gemma-4-31b-it:free",
            timeout_seconds=120,
            max_output_tokens=8192,
            data_collection="deny",
            debug_trace=None,
        )
        result = adapter.generate(requirement, analysis)

    assert result["model"] == "google/gemma-4-31b-it:free"


def test_openrouter_epic_adapter_maps_transport_failure() -> None:
    client = MagicMock()
    client.model = "google/gemma-4-31b-it:free"
    client.parse.side_effect = OpenRouterError("rate limited")
    with patch(
        "smb_requirement_agent.infrastructure.llm.openrouter_adapters._client_from_settings",
        return_value=client,
    ):
        adapter = OpenRouterEpicGenerator(
            base_url="https://router.example.test/api/v1",
            http_client=httpx.Client(),
            api_key="sk-or-private",
            model="google/gemma-4-31b-it:free",
            timeout_seconds=120,
            max_output_tokens=8192,
            data_collection="deny",
            debug_trace=None,
        )
    requirement = Requirement(
        RequirementId("requirement-1"),
        RequirementTitle("Bundle"),
        RequirementDescription("Make the bundle orderable."),
        RequirementStatus.DRAFT,
    )
    analysis = RequirementAnalysis(
        requirement_id=requirement.id,
        known_facts=(),
        constraints=(),
        business_rules=(),
        assumptions=(),
        open_questions=(),
        ambiguities=(),
        potential_dependencies=(),
    )

    with pytest.raises(EpicGenerationError, match="OpenRouter Epic generation failed"):
        adapter.generate(requirement, analysis)


def _embedding_adapter() -> OpenRouterKnowledgeEmbedding:
    return OpenRouterKnowledgeEmbedding(
        base_url="https://router.example.test/api/v1",
        http_client=httpx.Client(),
        api_key="sk-or-private",
        model="openai/text-embedding-3-small",
        timeout_seconds=120,
        data_collection="deny",
    )


def test_openrouter_embedding_is_ordered_private_and_768_dimensional() -> None:
    response = _response(
        {
            "data": [
                {"index": 1, "embedding": [0.2] * 768},
                {"index": 0, "embedding": [0.1] * 768},
            ]
        }
    )
    with patch(
        "smb_requirement_agent.infrastructure.llm.requirement_knowledge_adapters.httpx.Client.post",
        return_value=response,
    ) as post:
        result = _embedding_adapter().embed(("first", "second"))

    assert result[0][0] == 0.1
    assert result[1][0] == 0.2
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer sk-or-private"
    assert post.call_args.kwargs["json"] == {
        "model": "openai/text-embedding-3-small",
        "input": ["first", "second"],
        "dimensions": 768,
        "provider": {"data_collection": "deny"},
    }


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "invalid data"),
        ({"data": [{}]}, "invalid vectors"),
        ({"data": [{"index": 0, "embedding": ["bad"] * 768}]}, "non-numeric"),
        ({"data": [{"index": "0", "embedding": [0.1] * 768}]}, "invalid vector indices"),
        ({"data": [{"index": 0, "embedding": [0.1]}]}, "exactly 768"),
        ({"data": [{"index": 0, "embedding": [float("nan")] * 768}]}, "finite"),
        ({"data": []}, "returned 0 vectors"),
    ],
)
def test_openrouter_embedding_rejects_unusable_responses(payload: object, message: str) -> None:
    with (
        patch(
            "smb_requirement_agent.infrastructure.llm.requirement_knowledge_adapters."
            "httpx.Client.post",
            return_value=_response(payload),
        ),
        pytest.raises(KnowledgeGenerationError, match=message),
    ):
        _embedding_adapter().embed(("text",))


def test_openrouter_embedding_empty_input_avoids_provider_call() -> None:
    with patch(
        "smb_requirement_agent.infrastructure.llm.requirement_knowledge_adapters.httpx.Client.post"
    ) as post:
        assert _embedding_adapter().embed(()) == ()
    post.assert_not_called()


def test_openrouter_embedding_rejects_duplicate_indices() -> None:
    response = _response(
        {
            "data": [
                {"index": 0, "embedding": [0.1] * 768},
                {"index": 0, "embedding": [0.2] * 768},
            ]
        }
    )
    with (
        patch(
            "smb_requirement_agent.infrastructure.llm.requirement_knowledge_adapters."
            "httpx.Client.post",
            return_value=response,
        ),
        pytest.raises(KnowledgeGenerationError, match="invalid vector indices"),
    ):
        _embedding_adapter().embed(("first", "second"))


def test_openrouter_embedding_maps_http_failure() -> None:
    request = httpx.Request("POST", "https://router.example.test/api/v1/embeddings")
    failed = httpx.Response(500, request=request)
    response = _response({}, status_code=500)
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "provider failed", request=request, response=failed
    )

    with (
        patch(
            "smb_requirement_agent.infrastructure.llm.requirement_knowledge_adapters."
            "httpx.Client.post",
            return_value=response,
        ),
        pytest.raises(KnowledgeGenerationError, match="OpenRouter knowledge embedding failed"),
    ):
        _embedding_adapter().embed(("text",))
