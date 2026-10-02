"""Profile selection, shared transport contracts, safe errors and index isolation."""

from __future__ import annotations

import json
import math
from pathlib import Path
from threading import RLock
from typing import Any

import httpx
import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from smb_kernel.diagnostics import JsonLinesDebugTrace, NullDebugTrace
from smb_kernel.llm.compatible_transport import (
    CompatibleOutputError,
    CompatibleStructuredOutputClient,
    ConfiguredKnowledgeEmbedding,
)
from smb_kernel.llm.profiles import (
    EmbeddingProfile,
    ModelProfile,
    ProfileConfigurationError,
    load_profiles,
)
from smb_kernel.llm.structured_output import truncated

from smb_requirement_agent.application.errors import KnowledgeGenerationError, ModelTransportError
from smb_requirement_agent.application.public_errors import describe_public_error
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.infrastructure.config.options import ConfigurationError, LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence.knowledge_index_generations import (
    InMemoryKnowledgeIndexGenerations,
)
from smb_requirement_agent.infrastructure.persistence.requirement_knowledge_repository import (
    InMemoryRequirementKnowledgeStore,
)
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.error_handlers import register_error_handlers
from smb_requirement_agent.interfaces.cli.llm import main, validate_launcher


class Result(BaseModel):
    answer: str


def profile_data() -> dict[str, Any]:
    return {
        "version": 1,
        "default": "primary",
        "tasks": {"review": "other"},
        "embedding": "vectors",
        "profiles": {
            "primary": {
                "provider": "Gemini",
                "endpoint": "https://google.example/v1/",
                "model": "gemini-3.1-flash-lite",
                "api_key_env": "GEMINI_API_KEY",
                "images": True,
                "reasoning_effort": "minimal",
            },
            "other": {
                "provider": "Ollama",
                "endpoint": "http://localhost:11434/v1",
                "model": "local",
            },
            "unused": {
                "provider": "Other",
                "endpoint": "https://example.test/v1",
                "model": "other",
                "api_key_env": "UNUSED_KEY",
            },
        },
        "embeddings": {
            "vectors": {
                "provider": "Gemini",
                "protocol": "google",
                "endpoint": "https://google.example/v1beta",
                "model": "gemini-embedding-001",
                "api_key_env": "GEMINI_API_KEY",
            }
        },
    }


def write_config(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "llm.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_profiles_task_overrides_and_secret_exclusion(tmp_path: Path) -> None:
    config = load_profiles(
        str(write_config(tmp_path, profile_data())), {"GEMINI_API_KEY": "private-key"}
    )
    assert config.for_task("analysis").model == "gemini-3.1-flash-lite"
    assert config.for_task("review").model == "local"
    assert config.profiles["unused"].api_key is None
    assert config.selected_embedding.dimensions == 768
    assert "private-key" not in repr(config)
    assert "private-key" not in config.model_dump_json()
    assert "private-key" not in json.dumps(config.summary())
    assert (
        config.for_task("analysis").fingerprint
        == config.for_task("analysis").model_copy(update={"api_key": "replacement-key"}).fingerprint
    )


@pytest.mark.parametrize(
    "mutation", ["version", "task", "missing", "raw_key", "nested_auth", "endpoint", "budget"]
)
def test_configuration_rejects_invalid_or_unsafe_input(tmp_path: Path, mutation: str) -> None:
    data = profile_data()
    if mutation == "version":
        data["version"] = 2
    elif mutation == "task":
        data["tasks"] = {"unknown": "primary"}
    elif mutation == "missing":
        data["default"] = "absent"
    elif mutation == "raw_key":
        data["profiles"]["primary"]["api_key"] = "secret-value"
    elif mutation == "nested_auth":
        data["profiles"]["primary"]["request_options"] = {
            "extra_body": {"headers": {"Authorization": "secret-value"}}
        }
    elif mutation == "endpoint":
        data["profiles"]["primary"]["endpoint"] = "https://user:secret-value@example.test/v1"
    else:
        data["profiles"]["primary"]["context_tokens"] = 100
    with pytest.raises(ProfileConfigurationError) as failure:
        load_profiles(str(write_config(tmp_path, data)), {"GEMINI_API_KEY": "private-key"})
    assert "secret-value" not in str(failure.value)
    assert failure.value.__suppress_context__


def test_missing_selected_credentials_fail_locally(tmp_path: Path) -> None:
    with pytest.raises(ProfileConfigurationError, match="GEMINI_API_KEY"):
        load_profiles(str(write_config(tmp_path, profile_data())), {})


def test_settings_opt_in_and_launcher_conflicts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "smb_requirement_agent.infrastructure.config.settings.load_dotenv", lambda: None
    )
    monkeypatch.setenv("GEMINI_API_KEY", "private-key")
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("PERSISTENCE_PROVIDER", "memory")
    monkeypatch.delenv("LLM_CONFIG_PATH", raising=False)
    legacy = Settings.from_env()
    assert legacy.llm_provider is LLMProvider.FAKE
    path = write_config(tmp_path, profile_data())
    monkeypatch.setenv("LLM_CONFIG_PATH", str(path))
    settings = Settings.from_env()
    assert settings.llm_provider is LLMProvider.PROFILES
    validate_launcher(settings, None)
    with pytest.raises(ConfigurationError, match="conflicts"):
        validate_launcher(settings, "fake")
    validate_launcher(legacy, "fake")
    container = build_container(settings)
    try:
        assert container.rebuild_knowledge_index is not None
        assert container.knowledge_index_generations is not None
        generation = container.rebuild_knowledge_index.execute()
        assert generation.status == "active"
        assert not container.knowledge_index.pending_sources(1)
    finally:
        container.close_resources()


def test_check_command_does_not_make_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "private-key")
    monkeypatch.setenv("PERSISTENCE_PROVIDER", "memory")
    monkeypatch.setattr(
        httpx.Client, "post", lambda *args, **kwargs: pytest.fail("Paid request during check")
    )
    assert main(["check", "--config", str(write_config(tmp_path, profile_data()))]) == 0
    output = capsys.readouterr().out
    assert "no paid" in output and "private-key" not in output


def response(content: str = '{"answer":"ok"}', **kwargs: object) -> dict[str, object]:
    return {
        "choices": [{"finish_reason": "stop", "message": {"content": content}, **kwargs}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


@pytest.mark.parametrize(
    "name", ["gemini-flash-lite", "openai", "openrouter", "ollama", "compatible-template"]
)
def test_shared_profile_transport_contract(name: str) -> None:
    data = yaml.safe_load(Path("config/llm.yaml").read_text())
    p = ModelProfile.model_validate(data["profiles"][name]).model_copy(
        update={"api_key": "private-key"}
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=response())

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = CompatibleStructuredOutputClient(p, http, NullDebugTrace())
        assert (
            client.parse(
                system_prompt="Application instructions",
                user_prompt="Untrusted document",
                schema_type=Result,
            ).answer
            == "ok"
        )
    sent = json.loads(requests[0].content)
    assert sent["model"] == p.model and sent[p.output_parameter] == p.output_tokens
    assert sent["messages"][0]["content"].startswith("Application instructions")
    assert sent["messages"][1]["content"] == "Untrusted document"
    assert sent["response_format"]["type"] == p.structured_output
    assert requests[0].headers["authorization"] == "Bearer private-key"
    if name == "openrouter":
        assert sent["provider"]["allow_fallbacks"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [None]},
        response(""),
        response("not json"),
        response('{"answer":7}'),
        response('{"answer":"ok"}', finish_reason="length"),
        {"choices": [{"message": {"refusal": "unsafe", "content": '{"answer":"ok"}'}}]},
    ],
)
def test_malformed_refused_and_truncated_completions(payload: object) -> None:
    p = ModelProfile(provider="Test", endpoint="http://localhost/v1", model="test")
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    ) as http:
        with pytest.raises(ModelTransportError) as failure:
            CompatibleStructuredOutputClient(p, http, NullDebugTrace()).parse(
                system_prompt="app", user_prompt="source", schema_type=Result
            )
    assert failure.value.kind == "invalid_output"
    # Only a cut-off answer is marked as one, so a reader can ask for less (ADR-0091).
    assert truncated(failure.value) is (
        payload == response('{"answer":"ok"}', finish_reason="length")
    )


def test_images_rejected_before_request_and_sent_when_supported() -> None:
    p = ModelProfile(provider="Test", endpoint="http://localhost/v1", model="test")
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=response())

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = CompatibleStructuredOutputClient(p, http, NullDebugTrace())
        with pytest.raises(CompatibleOutputError, match="image"):
            client.parse(
                system_prompt="app",
                user_prompt="source",
                schema_type=Result,
                images=(("image/png", b"sanitized-image"),),
            )
        assert not sent
        CompatibleStructuredOutputClient(
            p.model_copy(update={"images": True}), http, NullDebugTrace()
        ).parse(
            system_prompt="app",
            user_prompt="source",
            schema_type=Result,
            images=(("image/png", b"sanitized-image"),),
        )
    assert sent[0]["messages"][1]["content"][1]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )


def test_timeout_is_not_retried() -> None:
    count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        raise httpx.ReadTimeout("secret provider details", request=request)

    p = ModelProfile(provider="Test", endpoint="http://localhost/v1", model="test")
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ModelTransportError) as failure:
            CompatibleStructuredOutputClient(p, http, NullDebugTrace()).parse(
                system_prompt="app", user_prompt="source", schema_type=Result
            )
    assert count == 1 and failure.value.kind == "timeout"
    assert "secret" not in str(failure.value)


@pytest.mark.parametrize(
    "status,attempts,kind",
    [
        (429, 3, "rate_limit"),
        (503, 3, "unavailable"),
        (401, 1, "authentication"),
        (400, 1, "configuration"),
    ],
)
def test_bounded_retries_and_safe_error_kinds(
    status: int, attempts: int, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    delays: list[float] = []
    monkeypatch.setattr("smb_kernel.llm.compatible_transport.time.sleep", delays.append)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, text="private-key", headers={"retry-after": "999"})

    p = ModelProfile(provider="Test", endpoint="http://localhost/v1", model="test")
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ModelTransportError) as failure:
            CompatibleStructuredOutputClient(p, http, NullDebugTrace()).parse(
                system_prompt="app", user_prompt="source", schema_type=Result
            )
    assert len(requests) == attempts and failure.value.kind == kind
    assert all(delay <= 10 for delay in delays)
    assert "private-key" not in str(failure.value)


def test_ollama_reasoning_fallback_remains_narrow() -> None:
    payload = {"choices": [{"message": {"content": "", "reasoning": '{"answer":"ok"}'}}]}
    p = ModelProfile(
        provider="Ollama",
        endpoint="http://localhost/v1",
        model="test",
        reasoning_effort="none",
        ollama_reasoning_fallback=True,
    )
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    ) as http:
        assert (
            CompatibleStructuredOutputClient(p, http, NullDebugTrace())
            .parse(system_prompt="app", user_prompt="source", schema_type=Result)
            .answer
            == "ok"
        )
        with pytest.raises(ModelTransportError):
            CompatibleStructuredOutputClient(
                p.model_copy(update={"ollama_reasoning_fallback": False}), http, NullDebugTrace()
            ).parse(system_prompt="app", user_prompt="source", schema_type=Result)
    with pytest.raises(ValidationError):
        ModelProfile(
            provider="Google",
            endpoint="https://example.test/v1",
            model="test",
            reasoning_effort="none",
            ollama_reasoning_fallback=True,
        )


@pytest.mark.parametrize("protocol", ["compatible", "google"])
def test_embeddings_order_dimensions_and_normalization(protocol: str) -> None:
    p = EmbeddingProfile.model_validate(
        {
            "provider": "Test",
            "protocol": protocol,
            "endpoint": "https://example.test/v1",
            "model": "embedding",
            "batch_size": 2,
        }
    )
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent.append(body)
        count = len(body["requests"] if protocol == "google" else body["input"])
        vectors = [[float(index + 1)] * 768 for index in range(count)]
        payload = (
            {"embeddings": [{"values": vector} for vector in vectors]}
            if protocol == "google"
            else {
                "data": [
                    {"index": index, "embedding": vector}
                    for index, vector in reversed(list(enumerate(vectors)))
                ]
            }
        )
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        vectors = ConfiguredKnowledgeEmbedding(p, http, NullDebugTrace()).embed(
            ("first", "second", "third")
        )
    assert len(sent) == 2 and len(vectors) == 3
    assert all(
        len(vector) == 768 and math.isclose(sum(x * x for x in vector), 1) for vector in vectors
    )
    if protocol == "google":
        assert sent[0]["requests"][0]["outputDimensionality"] == 768
    else:
        assert sent[0]["dimensions"] == 768


@pytest.mark.parametrize("issue", ["count", "dimension", "order", "zero", "type"])
def test_invalid_embeddings_are_rejected(issue: str) -> None:
    vector: list[object] = [1.0] * 768
    if issue == "dimension":
        vector = [1.0] * 767
    if issue == "zero":
        vector = [0.0] * 768
    if issue == "type":
        vector[0] = "bad"
    payload = {
        "data": []
        if issue == "count"
        else [{"index": 1 if issue == "order" else 0, "embedding": vector}]
    }
    p = EmbeddingProfile(provider="Test", endpoint="http://localhost/v1", model="test")
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    ) as http:
        with pytest.raises(KnowledgeGenerationError):
            ConfiguredKnowledgeEmbedding(p, http, NullDebugTrace()).embed(("source",))


def test_embedding_identity_tracks_meaningful_changes() -> None:
    p = EmbeddingProfile(provider="Test", endpoint="http://localhost/v1", model="test")
    for update in (
        {"endpoint": "http://other/v1"},
        {"model": "other"},
        {"preprocessing_version": "v2"},
        {"normalize": False},
    ):
        assert p.model_copy(update=update).identity != p.identity
    assert p.model_copy(update={"api_key": "new-secret"}).identity == p.identity


def test_resumable_generations_activation_races_and_rollback() -> None:
    lock = RLock()
    sources = InMemoryRequirementKnowledgeStore(lock)
    generations = InMemoryKnowledgeIndexGenerations(sources, lock)
    req = RequirementId("r1")
    sources.mark_source_changed(req)
    first = generations.begin_rebuild("old")
    assert generations.begin_rebuild("old").id == first.id
    old = generations.staging_index(first.id)
    assert old.replace_if_current(req, 1, "original", (), ())
    generations.activate(first.id)
    assert generations.active_index("old").indexed_fingerprint(req) == "original"
    with pytest.raises(ModelTransportError):
        generations.active_index("new").pending_sources(1)
    second = generations.begin_rebuild("new")
    new = generations.staging_index(second.id)
    sources.mark_source_changed(req)
    assert not new.replace_if_current(req, 1, "stale", (), ())
    with pytest.raises(ModelTransportError):
        generations.activate(second.id)
    assert new.replace_if_current(req, 2, "current", (), ())
    generations.activate(second.id)
    assert generations.active_index("new").indexed_fingerprint(req) == "current"
    with pytest.raises(ModelTransportError):
        generations.activate(first.id)
    assert old.replace_if_current(req, 2, "updated-old", (), ())
    generations.activate(first.id)
    assert generations.active_index("old").indexed_fingerprint(req) == "updated-old"
    state = generations.snapshot_state()
    generations.begin_rebuild("discard")
    generations.restore_state(state)
    assert len(generations.list_generations()) == 2


@pytest.mark.parametrize(
    "kind",
    [
        "timeout",
        "rate_limit",
        "authentication",
        "configuration",
        "invalid_output",
        "invalid_citations",
        "payment",
        "index_required",
    ],
)
def test_transport_errors_have_safe_ui_messages_and_http_status(kind: str) -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/fail")
    def fail() -> None:
        raise ModelTransportError(kind)

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/fail").status_code == 502
    error = ModelTransportError(kind)
    wrapper = KnowledgeGenerationError("unsafe detail")
    wrapper.__cause__ = error
    public = describe_public_error(wrapper)
    assert public.code == "model_" + kind
    assert public.message == str(error)


def test_diagnostics_redact_credentials_and_capture_usage(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    trace = JsonLinesDebugTrace(str(path), ("private-key",))
    p = ModelProfile(
        provider="Test", endpoint="http://localhost/v1", model="test", api_key="private-key"
    )
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response()))
    ) as http:
        CompatibleStructuredOutputClient(p, http, trace).parse(
            system_prompt="app", user_prompt="source", schema_type=Result
        )
    trace.record("config", config=p, authorization="Bearer private-key")
    trace.close()
    text = path.read_text()
    assert "private-key" not in text
    assert p.fingerprint in text and '"total_tokens":15' in text and "duration_ms" in text


def test_provider_options_cannot_shadow_routing_or_application_settings() -> None:
    safe = {"data_collection": "deny", "require_parameters": True, "allow_fallbacks": False}
    for options in (
        {"provider": safe, "extra_body": {"provider": {"allow_fallbacks": True}}},
        {"extra_body": {"reasoning_effort": "high"}},
        {"extra_body": {"tools": [{"type": "function"}]}},
        {"extra_body": "not an object"},
    ):
        with pytest.raises(ValidationError):
            ModelProfile(
                provider="OpenRouter",
                endpoint="https://openrouter.ai/api/v1",
                model="test",
                request_options=options,
            )


def test_provider_extras_and_output_parameter_are_transmitted() -> None:
    p = ModelProfile(
        provider="Test",
        endpoint="http://localhost/v1",
        model="test",
        output_parameter="max_completion_tokens",
        request_options={"extra_body": {"custom_setting": "enabled"}},
    )
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=response())

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        CompatibleStructuredOutputClient(p, http, NullDebugTrace()).parse(
            system_prompt="app", user_prompt="source", schema_type=Result
        )
    assert sent[0]["custom_setting"] == "enabled" and "extra_body" not in sent[0]
    assert sent[0]["max_completion_tokens"] == 8192 and "max_tokens" not in sent[0]


def test_context_budget_rejection_does_not_call_provider() -> None:
    p = ModelProfile(
        provider="Test",
        endpoint="http://localhost/v1",
        model="test",
        context_tokens=100,
        output_tokens=50,
    )
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: pytest.fail("Prompt exceeds budget"))
    ) as http:
        with pytest.raises(CompatibleOutputError, match="context budget"):
            CompatibleStructuredOutputClient(p, http, NullDebugTrace()).parse(
                system_prompt="app", user_prompt="x" * 1000, schema_type=Result
            )


def test_nonfinite_embedding_values_are_rejected() -> None:
    vector = [float("nan"), *([1.0] * 767)]
    p = EmbeddingProfile(provider="Test", endpoint="http://localhost/v1", model="test")
    payload = json.dumps({"data": [{"index": 0, "embedding": vector}]}).encode()
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, content=payload))
    ) as http:
        with pytest.raises(KnowledgeGenerationError):
            ConfiguredKnowledgeEmbedding(p, http, NullDebugTrace()).embed(("source",))


def test_google_embeddings_require_normalization() -> None:
    with pytest.raises(ValidationError):
        EmbeddingProfile(
            provider="Google",
            protocol="google",
            endpoint="https://example.test/v1",
            model="test",
            normalize=False,
        )
