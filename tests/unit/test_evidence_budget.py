"""Evidence packets keep their budget; consolidation and one pass follow the model (ADR-0029)."""

from __future__ import annotations

from smb_kernel.llm.profiles import load_profiles

from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.composition.analysis import (
    _consolidation_budget,
    _evidence_budget,
    _output_characters,
)


def _openrouter(context_tokens: int | None = None) -> Settings:
    return Settings(
        llm_provider=LLMProvider.OPENROUTER,
        openrouter_api_key="sk-or-test",
        openrouter_max_output_tokens=32_768,
        openrouter_context_tokens=context_tokens,
    )


def test_openrouter_without_a_window_keeps_the_default_for_both() -> None:
    settings = _openrouter()

    assert _evidence_budget(settings) == 60_000
    assert _consolidation_budget(settings) == 60_000


def test_openrouter_window_raises_only_the_consolidation_budget() -> None:
    settings = _openrouter(400_000)

    assert _evidence_budget(settings) == 60_000
    assert _consolidation_budget(settings) == (400_000 - 32_768) * 4


def test_a_profile_window_raises_consolidation_but_never_section_packets() -> None:
    # The bundled default profile: a 1M-token window with an 8192-token output limit.
    profiles = load_profiles("config/llm.yaml", {"GEMINI_API_KEY": "private-key"})
    settings = Settings(llm_provider=LLMProvider.FAKE, llm_profiles=profiles)

    assert _evidence_budget(settings) == 60_000
    assert _consolidation_budget(settings) == (1_048_576 - 8192) * 4


def test_a_small_local_window_bounds_both_budgets() -> None:
    settings = Settings(
        llm_provider=LLMProvider.LOCAL,
        local_llm_model="local-model",
        local_embedding_model="local-embedding",
        local_llm_context_window_tokens=16_384,
        local_llm_max_output_tokens=8192,
    )

    assert _evidence_budget(settings) == (16_384 - 8192) * 4
    assert _consolidation_budget(settings) == (16_384 - 8192) * 4


def test_one_pass_is_bounded_by_the_analysis_model_output_limit() -> None:
    profiles = load_profiles("config/llm.yaml", {"GEMINI_API_KEY": "private-key"})
    local = Settings(
        llm_provider=LLMProvider.LOCAL,
        local_llm_model="local-model",
        local_embedding_model="local-embedding",
        local_llm_context_window_tokens=16_384,
        local_llm_max_output_tokens=8192,
    )

    assert _output_characters(_openrouter(400_000)) == 32_768 * 4
    assert _output_characters(Settings(llm_provider=LLMProvider.FAKE, llm_profiles=profiles)) == (
        8192 * 4
    )
    assert _output_characters(local) == 8192 * 4


def test_an_unknown_output_limit_never_allows_one_pass() -> None:
    assert _output_characters(Settings(llm_provider=LLMProvider.FAKE)) == 0
