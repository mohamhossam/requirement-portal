"""Actual embedding-model counting, with no chat-model or byte-count fallback."""

import json
from pathlib import Path

import httpx
import pytest

from smb_requirement_agent.application.errors import ModelTransportError
from smb_requirement_agent.application.use_cases.qualify_chunk_tokens import qualify_chunk_tokens
from smb_requirement_agent.infrastructure.config.llm_profiles import EmbeddingProfile
from smb_requirement_agent.infrastructure.diagnostics import NullDebugTrace
from smb_requirement_agent.infrastructure.llm.compatible_transport import (
    GoogleEmbeddingTokenCounter,
)


def test_qualification_fixture_matches_actual_reviewed_chunk_output() -> None:
    from tests.chunk_token_fixtures import chunk_token_samples

    saved = json.loads(
        Path("docs/evaluation/chunk-token-fixtures.json").read_text(encoding="utf-8")
    )
    assert saved == [{"case": case, "text": text} for case, text in chunk_token_samples()]


def profile() -> EmbeddingProfile:
    return EmbeddingProfile(
        provider="Google",
        protocol="google",
        endpoint="https://provider.example/v1beta",
        model="gemini-embedding-001",
        api_key="synthetic-key",
    )


def test_qualification_calls_the_embedding_model_with_exact_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1beta/models/gemini-embedding-001:countTokens"
        assert json.loads(request.content) == {
            "contents": [{"parts": [{"text": "التغطية Coverage"}]}]
        }
        assert request.headers["x-goog-api-key"] == "synthetic-key"
        return httpx.Response(200, json={"totalTokens": 7})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        result = qualify_chunk_tokens(
            GoogleEmbeddingTokenCounter(profile(), http, NullDebugTrace()),
            (("mixed", "التغطية Coverage"),),
            2048,
        )
    assert result["all_within_model_limit"] is True
    assert "7" in str(result["measurements"])
    assert "synthetic-key" not in str(result)


@pytest.mark.parametrize(
    "payload",
    [{}, [], {"totalTokens": True}, {"totalTokens": -1}, {"totalTokens": 0}, {"totalTokens": "7"}],
)
def test_invalid_count_is_explicit_failure_never_utf8_fallback(payload: object) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as http:
        with pytest.raises(ModelTransportError, match="invalid"):
            GoogleEmbeddingTokenCounter(profile(), http, NullDebugTrace()).count("hello")


def test_unsupported_endpoint_never_uses_a_chat_tokenizer() -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(404))) as http:
        with pytest.raises(ModelTransportError):
            GoogleEmbeddingTokenCounter(profile(), http, NullDebugTrace()).count("hello")
        with pytest.raises(ModelTransportError):
            GoogleEmbeddingTokenCounter(
                profile().model_copy(update={"protocol": "compatible"}), http, NullDebugTrace()
            )


def test_measurement_above_limit_fails_qualification() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"totalTokens": 2049}))
    ) as http:
        result = qualify_chunk_tokens(
            GoogleEmbeddingTokenCounter(profile(), http, NullDebugTrace()),
            (("oversized", "text"),),
            2048,
        )
    assert result["all_within_model_limit"] is False
