"""The OpenAI transport behind the shared structured-generation adapters."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx2
import openai
import pytest
from pydantic import BaseModel
from smb_kernel.llm.openai_structured_output import (
    OpenAIStructuredOutputClient,
)
from smb_kernel.llm.structured_output import StructuredOutputError

from smb_requirement_agent.application.public_errors import describe_public_error
from smb_requirement_agent.infrastructure.config.options import ConfigurationError, LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings

REQUEST = httpx2.Request("POST", "https://api.openai.test/v1/chat/completions")


class Answer(BaseModel):
    text: str


def _client(parse: MagicMock) -> OpenAIStructuredOutputClient:
    sdk = MagicMock()
    sdk.chat.completions.parse = parse
    return OpenAIStructuredOutputClient(sdk, model="gpt-test", timeout_seconds=12.5)


def _reply(parsed: object | None) -> MagicMock:
    choice = MagicMock()
    choice.message.parsed = parsed
    response = MagicMock()
    response.choices = [choice]
    return MagicMock(return_value=response)


def test_parse_sends_the_configured_model_timeout_and_schema() -> None:
    parse = _reply(Answer(text="ok"))

    result = _client(parse).parse(system_prompt="sys", user_prompt="user", schema_type=Answer)

    assert result == Answer(text="ok")
    kwargs = parse.call_args.kwargs
    assert (kwargs["model"], kwargs["timeout"], kwargs["response_format"]) == (
        "gpt-test",
        12.5,
        Answer,
    )
    assert kwargs["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user"},
    ]


def test_images_are_sent_as_separate_data_url_parts() -> None:
    parse = _reply(Answer(text="ok"))

    _client(parse).parse(
        system_prompt="sys",
        user_prompt="user",
        schema_type=Answer,
        images=(("image/png", b"\x89PNG"),),
    )

    content = parse.call_args.kwargs["messages"][1]["content"]
    assert content[0] == {"type": "text", "text": "user"}
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (openai.APITimeoutError(request=REQUEST), "model_timeout"),
        (
            openai.RateLimitError(
                "slow down", response=httpx2.Response(429, request=REQUEST), body=None
            ),
            "model_rate_limit",
        ),
        (
            openai.AuthenticationError(
                "bad key", response=httpx2.Response(401, request=REQUEST), body=None
            ),
            "model_authentication",
        ),
        (
            openai.BadRequestError(
                "bad model", response=httpx2.Response(400, request=REQUEST), body=None
            ),
            "model_configuration",
        ),
        (openai.APIConnectionError(request=REQUEST), "model_unavailable"),
    ],
)
def test_sdk_failures_become_public_error_kinds_without_provider_text(
    error: openai.OpenAIError, code: str
) -> None:
    with pytest.raises(StructuredOutputError) as raised:
        _client(MagicMock(side_effect=error)).parse(
            system_prompt="sys", user_prompt="user", schema_type=Answer
        )

    public = describe_public_error(raised.value)
    assert public.code == code
    assert "slow down" not in public.message and "bad key" not in public.message


@pytest.mark.parametrize("parsed", [None])
def test_empty_or_refused_output_is_invalid_output(parsed: object | None) -> None:
    with pytest.raises(StructuredOutputError) as raised:
        _client(_reply(parsed)).parse(system_prompt="sys", user_prompt="user", schema_type=Answer)

    assert describe_public_error(raised.value).code == "model_invalid_output"


def test_no_choices_is_invalid_output() -> None:
    response = MagicMock()
    response.choices = []

    with pytest.raises(StructuredOutputError) as raised:
        _client(MagicMock(return_value=response)).parse(
            system_prompt="sys", user_prompt="user", schema_type=Answer
        )

    assert describe_public_error(raised.value).code == "model_invalid_output"


def test_openai_timeout_is_configurable_and_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "45")
    assert Settings.from_env().openai_timeout_seconds == 45.0

    with pytest.raises(ConfigurationError, match="OPENAI_TIMEOUT_SECONDS"):
        Settings(llm_provider=LLMProvider.FAKE, openai_timeout_seconds=0)
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "soon")
    with pytest.raises(ConfigurationError, match="OPENAI_TIMEOUT_SECONDS"):
        Settings.from_env()
