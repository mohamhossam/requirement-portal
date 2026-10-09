"""Tests for configuration resolution and the composition root."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from smb_kernel.observability.metrics import Metrics

from smb_requirement_agent.analysis.infrastructure.llm.fake_requirement_analyzer import (
    FakeRequirementAnalyzer,
)
from smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer import (
    LocalRequirementAnalyzer,
)
from smb_requirement_agent.analysis.infrastructure.llm.openai_adapters import (
    OpenAIRequirementAnalyzer,
)
from smb_requirement_agent.analysis.infrastructure.llm.openrouter_adapters import (
    OpenRouterRequirementAnalyzer,
)
from smb_requirement_agent.breakdown.infrastructure.llm.local_epic_generator import (
    LocalEpicGenerator,
)
from smb_requirement_agent.breakdown.infrastructure.llm.local_feature_generator import (
    LocalFeatureGenerator,
)
from smb_requirement_agent.breakdown.infrastructure.llm.local_story_generator import (
    LocalStoryGenerator,
)
from smb_requirement_agent.breakdown.infrastructure.llm.local_story_quality_evaluator import (
    LocalStoryQualityEvaluator,
)
from smb_requirement_agent.breakdown.infrastructure.llm.openai_adapters import (
    OpenAIStoryQualityEvaluator,
)
from smb_requirement_agent.breakdown.infrastructure.llm.openrouter_adapters import (
    OpenRouterEpicGenerator,
    OpenRouterFeatureGenerator,
    OpenRouterStoryGenerator,
    OpenRouterStoryQualityEvaluator,
)
from smb_requirement_agent.infrastructure.config.options import (
    DEFAULT_AI_JOB_MAX_ATTEMPTS,
    DEFAULT_LOCAL_LLM_BASE_URL,
    DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS,
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OPENROUTER_BASE_URL,
    DEFAULT_OPENROUTER_EMBEDDING_MODEL,
    DEFAULT_OPENROUTER_MAX_OUTPUT_TOKENS,
    DEFAULT_OPENROUTER_MODEL,
    DEFAULT_OPENROUTER_TIMEOUT_SECONDS,
    ConfigurationError,
    IdentityProvider,
    LLMProvider,
    LogFormat,
    PersistenceProvider,
)
from smb_requirement_agent.infrastructure.config.settings import PersistenceSettings, Settings
from smb_requirement_agent.interfaces.api.composition import llm as composition
from smb_requirement_agent.interfaces.api.composition.llm import build_llm_adapters
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.knowledge.infrastructure.llm.fake_requirement_knowledge import (
    FakeKnowledgeEmbedding,
)
from smb_requirement_agent.knowledge.infrastructure.llm.openrouter_adapters import (
    OpenRouterClarificationAnswerSuggester,
    OpenRouterRequirementRelationshipClassifier,
)
from smb_requirement_agent.knowledge.infrastructure.llm.requirement_knowledge_adapters import (
    LocalKnowledgeEmbedding,
    OpenAIKnowledgeEmbedding,
    OpenRouterKnowledgeEmbedding,
)


def _no_spend(tokens: int) -> None:
    """These tests make no model calls, so nothing is spent."""


class TestSettings:
    def test_openai_provider_without_a_key_fails_loudly(self) -> None:
        """A missing key must fail at construction, not on the first request."""
        with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
            Settings(llm_provider=LLMProvider.OPENAI, openai_api_key=None)

    def test_fake_provider_needs_no_credentials(self) -> None:
        settings = Settings(llm_provider=LLMProvider.FAKE)

        assert settings.openai_api_key is None

    def test_openrouter_provider_requires_a_key(self) -> None:
        with pytest.raises(ConfigurationError, match="OPENROUTER_API_KEY"):
            Settings(llm_provider=LLMProvider.OPENROUTER)

    @pytest.mark.parametrize(
        ("changes", "message"),
        [
            ({"openrouter_base_url": "http://openrouter.example.test/v1"}, "HTTPS"),
            ({"openrouter_timeout_seconds": 0}, "OPENROUTER_TIMEOUT_SECONDS"),
            ({"openrouter_max_output_tokens": 0}, "OPENROUTER_MAX_OUTPUT_TOKENS"),
            ({"openrouter_model": " "}, "OPENROUTER_MODEL"),
            ({"openrouter_embedding_model": " "}, "OPENROUTER_EMBEDDING_MODEL"),
            ({"openrouter_data_collection": "allow"}, "OPENROUTER_DATA_COLLECTION"),
            ({"openrouter_data_collection": "sometimes"}, "OPENROUTER_DATA_COLLECTION"),
        ],
    )
    def test_openrouter_provider_validates_configuration(
        self, changes: dict[str, object], message: str
    ) -> None:
        with pytest.raises(ConfigurationError, match=message):
            Settings(
                llm_provider=LLMProvider.OPENROUTER,
                openrouter_api_key="sk-or-test",
                **changes,  # type: ignore[arg-type]
            )

    def test_oidc_provider_requires_complete_secure_configuration(self) -> None:
        with pytest.raises(ConfigurationError, match="OIDC_ISSUER_URL"):
            Settings(
                llm_provider=LLMProvider.FAKE,
                identity_provider=IdentityProvider.OIDC,
            )

        with pytest.raises(ConfigurationError, match="absolute HTTPS URL"):
            Settings(
                llm_provider=LLMProvider.FAKE,
                identity_provider=IdentityProvider.OIDC,
                oidc_issuer_url="http://identity.example.test",
                oidc_audience="smb-api",
                oidc_client_id="smb-spa",
            )

    @pytest.mark.parametrize("algorithm", ["HS256", "RSgarbage"])
    def test_oidc_provider_rejects_unsafe_or_unknown_algorithms(self, algorithm: str) -> None:
        with pytest.raises(ConfigurationError, match="supported asymmetric"):
            Settings(
                llm_provider=LLMProvider.FAKE,
                identity_provider=IdentityProvider.OIDC,
                oidc_issuer_url="https://identity.example.test",
                oidc_audience="smb-api",
                oidc_client_id="smb-spa",
                oidc_allowed_algorithms=(algorithm,),
            )

    def test_from_env_reads_oidc_configuration(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.setenv("IDENTITY_PROVIDER", "oidc")
        monkeypatch.setenv("OIDC_ISSUER_URL", "https://identity.example.test/")
        monkeypatch.setenv("OIDC_AUDIENCE", "smb-api")
        monkeypatch.setenv("OIDC_CLIENT_ID", "smb-spa")
        monkeypatch.setenv("OIDC_SCOPES", "openid profile")
        monkeypatch.setenv("OIDC_ALLOWED_ALGORITHMS", "RS256, PS256")
        monkeypatch.setenv("OIDC_JWKS_TTL_SECONDS", "600")
        monkeypatch.setenv("OIDC_UNKNOWN_KEY_TTL_SECONDS", "20")
        monkeypatch.setenv("OIDC_UNKNOWN_KEY_CACHE_SIZE", "128")
        monkeypatch.setenv("OIDC_COMPANY_SSO_ENABLED", "true")
        monkeypatch.setenv("OIDC_COMPANY_SSO_ALIAS", "entra-company")
        monkeypatch.setenv("OIDC_PASSWORD_LOGIN_ENABLED", "false")

        settings = Settings.from_env()

        assert settings.identity_provider is IdentityProvider.OIDC
        assert settings.oidc_issuer_url == "https://identity.example.test"
        assert settings.oidc_audience == "smb-api"
        assert settings.oidc_client_id == "smb-spa"
        assert settings.oidc_scopes == "openid profile"
        assert settings.oidc_allowed_algorithms == ("RS256", "PS256")
        assert settings.oidc_jwks_ttl_seconds == 600
        assert settings.oidc_unknown_key_ttl_seconds == 20
        assert settings.oidc_unknown_key_cache_size == 128
        assert settings.oidc_company_sso_enabled is True
        assert settings.oidc_company_sso_alias == "entra-company"
        assert settings.oidc_password_login_enabled is False

    def test_oidc_provider_requires_a_login_choice_and_company_alias(self) -> None:
        with pytest.raises(ConfigurationError, match="At least one OIDC login choice"):
            Settings(
                llm_provider=LLMProvider.FAKE,
                identity_provider=IdentityProvider.OIDC,
                oidc_issuer_url="https://identity.example.test",
                oidc_audience="smb-api",
                oidc_client_id="smb-spa",
                oidc_company_sso_enabled=False,
                oidc_password_login_enabled=False,
            )
        with pytest.raises(ConfigurationError, match="OIDC_COMPANY_SSO_ALIAS"):
            Settings(
                llm_provider=LLMProvider.FAKE,
                identity_provider=IdentityProvider.OIDC,
                oidc_issuer_url="https://identity.example.test",
                oidc_audience="smb-api",
                oidc_client_id="smb-spa",
                oidc_company_sso_alias=" ",
            )

    @pytest.mark.parametrize("name", ["OIDC_COMPANY_SSO_ENABLED", "OIDC_PASSWORD_LOGIN_ENABLED"])
    def test_from_env_rejects_invalid_oidc_choice_flags(
        self, monkeypatch: pytest.MonkeyPatch, name: str
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.setenv(name, "sometimes")

        with pytest.raises(ConfigurationError, match=name):
            Settings.from_env()

    def test_oidc_provider_rejects_invalid_key_cache_limits(self) -> None:
        with pytest.raises(ConfigurationError, match="cache TTL"):
            Settings(
                llm_provider=LLMProvider.FAKE,
                identity_provider=IdentityProvider.OIDC,
                oidc_issuer_url="https://identity.example.test",
                oidc_audience="smb-api",
                oidc_client_id="smb-spa",
                oidc_jwks_ttl_seconds=0,
            )
        with pytest.raises(ConfigurationError, match="CACHE_SIZE"):
            Settings(
                llm_provider=LLMProvider.FAKE,
                identity_provider=IdentityProvider.OIDC,
                oidc_issuer_url="https://identity.example.test",
                oidc_audience="smb-api",
                oidc_client_id="smb-spa",
                oidc_unknown_key_cache_size=0,
            )

    def test_local_provider_requires_a_model_identifier(self) -> None:
        with pytest.raises(ConfigurationError, match="LOCAL_LLM_MODEL"):
            Settings(llm_provider=LLMProvider.LOCAL)

    def test_local_provider_requires_an_embedding_model_identifier(self) -> None:
        with pytest.raises(ConfigurationError, match="LOCAL_EMBEDDING_MODEL"):
            Settings(llm_provider=LLMProvider.LOCAL, local_llm_model="qwen-local")

    def test_local_provider_validates_url_and_timeout(self) -> None:
        with pytest.raises(ConfigurationError, match="LOCAL_LLM_BASE_URL"):
            Settings(
                llm_provider=LLMProvider.LOCAL,
                local_llm_model="model",
                local_embedding_model="embedding-768",
                local_llm_base_url="localhost:1234/v1",
            )
        with pytest.raises(ConfigurationError, match="LOCAL_LLM_TIMEOUT_SECONDS"):
            Settings(
                llm_provider=LLMProvider.LOCAL,
                local_llm_model="model",
                local_embedding_model="embedding-768",
                local_llm_timeout_seconds=0,
            )
        with pytest.raises(ConfigurationError, match="LOCAL_LLM_REASONING_EFFORT"):
            Settings(
                llm_provider=LLMProvider.LOCAL,
                local_llm_model="model",
                local_embedding_model="embedding-768",
                local_llm_reasoning_effort="maximum",
            )

    def test_from_env_reads_provider_key_and_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")

        settings = Settings.from_env()

        assert settings.llm_provider is LLMProvider.OPENAI
        assert settings.openai_api_key == "sk-test"
        assert settings.openai_model == "gpt-4o-mini"

    def test_from_env_defaults_the_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        assert Settings.from_env().openai_model == DEFAULT_OPENAI_MODEL
        assert Settings.from_env().openai_embedding_model == DEFAULT_OPENAI_EMBEDDING_MODEL

    def test_ai_job_max_attempts_defaults_to_three_and_is_read(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.delenv("AI_JOB_MAX_ATTEMPTS", raising=False)
        assert Settings.from_env().ai_job_max_attempts == DEFAULT_AI_JOB_MAX_ATTEMPTS == 3

        monkeypatch.setenv("AI_JOB_MAX_ATTEMPTS", "5")
        assert Settings.from_env().ai_job_max_attempts == 5

    @pytest.mark.parametrize(("value", "message"), [("0", "at least 1"), ("many", "numeric")])
    def test_ai_job_max_attempts_must_be_a_positive_integer(
        self, monkeypatch: pytest.MonkeyPatch, value: str, message: str
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.setenv("AI_JOB_MAX_ATTEMPTS", value)

        with pytest.raises(ConfigurationError, match=message):
            Settings.from_env()

    def test_ai_job_retry_backoff_defaults_and_is_read(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.delenv("AI_JOB_RETRY_FIRST_SECONDS", raising=False)
        monkeypatch.delenv("AI_JOB_RETRY_MAX_SECONDS", raising=False)
        defaults = Settings.from_env()
        assert (defaults.ai_job_retry_first_seconds, defaults.ai_job_retry_max_seconds) == (
            30.0,
            300.0,
        )

        monkeypatch.setenv("AI_JOB_RETRY_FIRST_SECONDS", "5")
        monkeypatch.setenv("AI_JOB_RETRY_MAX_SECONDS", "40")
        read = Settings.from_env()
        assert (read.ai_job_retry_first_seconds, read.ai_job_retry_max_seconds) == (5.0, 40.0)

    @pytest.mark.parametrize(
        ("first", "longest", "message"),
        [("0", "300", "greater than zero"), ("60", "30", "no more than"), ("soon", "1", "numeric")],
    )
    def test_ai_job_retry_backoff_must_be_positive_and_ordered(
        self, monkeypatch: pytest.MonkeyPatch, first: str, longest: str, message: str
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.setenv("AI_JOB_RETRY_FIRST_SECONDS", first)
        monkeypatch.setenv("AI_JOB_RETRY_MAX_SECONDS", longest)

        with pytest.raises(ConfigurationError, match=message):
            Settings.from_env()

    def test_from_env_reads_local_provider_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "local")
        monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen-local")
        monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", "embedding-768")
        monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
        monkeypatch.setenv("LOCAL_LLM_TIMEOUT_SECONDS", "45.5")
        monkeypatch.setenv("LOCAL_LLM_REASONING_EFFORT", "none")
        monkeypatch.setenv("LOCAL_LLM_VISION_ENABLED", "true")

        settings = Settings.from_env()

        assert settings.llm_provider is LLMProvider.LOCAL
        assert settings.local_llm_model == "qwen-local"
        assert settings.local_embedding_model == "embedding-768"
        assert settings.local_llm_base_url == "http://127.0.0.1:11434/v1"
        assert settings.local_llm_timeout_seconds == 45.5
        assert settings.local_llm_reasoning_effort == "none"
        assert settings.local_llm_vision_enabled is True

    def test_from_env_reads_openrouter_provider_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        monkeypatch.setenv("OPENROUTER_MODEL", "google/gemma-4-31b-it")
        monkeypatch.setenv("OPENROUTER_EMBEDDING_MODEL", "openai/text-embedding-3-small")
        monkeypatch.setenv("OPENROUTER_BASE_URL", "https://router.example.test/api/v1")
        monkeypatch.setenv("OPENROUTER_TIMEOUT_SECONDS", "45.5")
        monkeypatch.setenv("OPENROUTER_MAX_OUTPUT_TOKENS", "4096")
        monkeypatch.setenv("OPENROUTER_DATA_COLLECTION", "deny")

        settings = Settings.from_env()

        assert settings.llm_provider is LLMProvider.OPENROUTER
        assert settings.openrouter_api_key == "sk-or-test"
        assert settings.openrouter_model == "google/gemma-4-31b-it"
        assert settings.openrouter_embedding_model == "openai/text-embedding-3-small"
        assert settings.openrouter_base_url == "https://router.example.test/api/v1"
        assert settings.openrouter_timeout_seconds == 45.5
        assert settings.openrouter_max_output_tokens == 4096
        assert settings.openrouter_data_collection == "deny"

    def test_non_openrouter_provider_ignores_invalid_openrouter_numbers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.setenv("OPENROUTER_TIMEOUT_SECONDS", "not-a-number")
        monkeypatch.setenv("OPENROUTER_MAX_OUTPUT_TOKENS", "not-an-integer")

        settings = Settings.from_env()

        assert settings.llm_provider is LLMProvider.FAKE
        assert settings.openrouter_timeout_seconds == DEFAULT_OPENROUTER_TIMEOUT_SECONDS
        assert settings.openrouter_max_output_tokens == DEFAULT_OPENROUTER_MAX_OUTPUT_TOKENS

    @pytest.mark.parametrize(
        ("name", "value", "message"),
        [
            ("OPENROUTER_TIMEOUT_SECONDS", "slow", "must be a number"),
            ("OPENROUTER_MAX_OUTPUT_TOKENS", "many", "must be an integer"),
        ],
    )
    def test_openrouter_rejects_non_numeric_limits_from_environment(
        self,
        monkeypatch: pytest.MonkeyPatch,
        name: str,
        value: str,
        message: str,
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        monkeypatch.setenv(name, value)

        with pytest.raises(ConfigurationError, match=message):
            Settings.from_env()

    def test_openrouter_key_is_not_in_settings_repr(self) -> None:
        settings = Settings(
            llm_provider=LLMProvider.OPENROUTER,
            openrouter_api_key="sk-or-private",
        )

        assert "sk-or-private" not in repr(settings)

    def test_from_env_defaults_openrouter_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        for name in (
            "OPENROUTER_MODEL",
            "OPENROUTER_EMBEDDING_MODEL",
            "OPENROUTER_BASE_URL",
            "OPENROUTER_TIMEOUT_SECONDS",
            "OPENROUTER_MAX_OUTPUT_TOKENS",
            "OPENROUTER_DATA_COLLECTION",
        ):
            monkeypatch.setenv(name, "")

        settings = Settings.from_env()

        assert settings.openrouter_model == DEFAULT_OPENROUTER_MODEL
        assert settings.openrouter_embedding_model == DEFAULT_OPENROUTER_EMBEDDING_MODEL
        assert settings.openrouter_base_url == DEFAULT_OPENROUTER_BASE_URL
        assert settings.openrouter_timeout_seconds == DEFAULT_OPENROUTER_TIMEOUT_SECONDS
        assert settings.openrouter_max_output_tokens == DEFAULT_OPENROUTER_MAX_OUTPUT_TOKENS
        assert settings.openrouter_data_collection == "deny"

    def test_from_env_reads_opt_in_debug_trace_configuration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.setenv("DEBUG_TRACE_ENABLED", "true")
        monkeypatch.setenv("DEBUG_TRACE_PATH", "logs/provider-debug.log")

        settings = Settings.from_env()

        assert settings.debug_trace_enabled is True
        assert settings.debug_trace_path == "logs/provider-debug.log"

    def test_from_env_rejects_invalid_debug_trace_declaration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.setenv("DEBUG_TRACE_ENABLED", "sometimes")

        with pytest.raises(ConfigurationError, match="DEBUG_TRACE_ENABLED"):
            Settings.from_env()

    def test_from_env_rejects_invalid_local_vision_declaration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.setenv("LOCAL_LLM_VISION_ENABLED", "auto")

        with pytest.raises(ConfigurationError, match="must be true or false"):
            Settings.from_env()

    def test_from_env_defaults_local_url_and_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "local")
        monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen-local")
        monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", "embedding-768")
        # Empty process values mask any developer-local `.env` entries while
        # still exercising Settings' documented defaults.
        monkeypatch.setenv("LOCAL_LLM_BASE_URL", "")
        monkeypatch.setenv("LOCAL_LLM_TIMEOUT_SECONDS", "")
        monkeypatch.setenv("LOCAL_LLM_REASONING_EFFORT", "")

        settings = Settings.from_env()

        assert settings.local_llm_base_url == DEFAULT_LOCAL_LLM_BASE_URL
        assert settings.local_llm_timeout_seconds == DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS
        assert settings.local_llm_reasoning_effort is None

    def test_from_env_rejects_non_numeric_local_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "local")
        monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen-local")
        monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", "embedding-768")
        monkeypatch.setenv("LOCAL_LLM_TIMEOUT_SECONDS", "slow")

        with pytest.raises(ConfigurationError, match="must be a number"):
            Settings.from_env()

    def test_from_env_rejects_an_unknown_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "gemini")

        with pytest.raises(ConfigurationError, match="Unsupported LLM_PROVIDER"):
            Settings.from_env()

    def test_postgres_requires_database_url(self) -> None:
        with pytest.raises(ConfigurationError, match="DATABASE_URL"):
            Settings(
                llm_provider=LLMProvider.FAKE,
                persistence_provider=PersistenceProvider.POSTGRES,
            )

    def test_persistence_settings_do_not_require_llm_configuration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("PERSISTENCE_PROVIDER", "postgres")
        monkeypatch.setenv("DATABASE_URL", "postgresql://database.example.test/app")

        settings = PersistenceSettings.from_env()

        assert settings.provider is PersistenceProvider.POSTGRES
        assert settings.database_url == "postgresql://database.example.test/app"

    def test_from_env_reads_document_limits_and_storage_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.setenv("DOCUMENT_MAX_FILE_BYTES", "2048")
        monkeypatch.setenv("DOCUMENT_CONTEXT_MAX_CHARACTERS", "4096")
        monkeypatch.setenv("DOCUMENT_STORAGE_PATH", "durable/documents")

        settings = Settings.from_env()

        assert settings.document_max_file_bytes == 2048
        assert settings.document_context_max_characters == 4096
        assert settings.document_storage_path == "durable/documents"

    def test_document_limits_and_storage_path_are_validated(self) -> None:
        with pytest.raises(ConfigurationError, match="DOCUMENT_MAX_FILE_BYTES"):
            Settings(llm_provider=LLMProvider.FAKE, document_max_file_bytes=0)
        with pytest.raises(ConfigurationError, match="DOCUMENT_CONTEXT_MAX_CHARACTERS"):
            Settings(llm_provider=LLMProvider.FAKE, document_context_max_characters=0)
        with pytest.raises(ConfigurationError, match="DOCUMENT_STORAGE_PATH"):
            Settings(llm_provider=LLMProvider.FAKE, document_storage_path="  ")

    def test_local_context_budget_is_validated(self) -> None:
        with pytest.raises(ConfigurationError, match="smaller than"):
            Settings(
                llm_provider=LLMProvider.LOCAL,
                local_llm_model="qwen-local",
                local_embedding_model="embedding-768",
                local_llm_context_window_tokens=4096,
                local_llm_max_output_tokens=4096,
            )


class TestContainer:
    def test_fake_provider_selects_the_fake_analyzer(self) -> None:
        adapters = build_llm_adapters(Settings(llm_provider=LLMProvider.FAKE), Metrics(), _no_spend)

        assert isinstance(adapters.analyzer, FakeRequirementAnalyzer)
        assert isinstance(adapters.knowledge_embedding, FakeKnowledgeEmbedding)

    def test_openai_provider_selects_the_openai_analyzer(self) -> None:
        settings = Settings(llm_provider=LLMProvider.OPENAI, openai_api_key="sk-test")

        assert isinstance(
            build_llm_adapters(settings, Metrics(), _no_spend).analyzer, OpenAIRequirementAnalyzer
        )

    def test_local_provider_selects_all_local_adapters(self) -> None:
        settings = Settings(
            llm_provider=LLMProvider.LOCAL,
            local_llm_model="qwen-local",
            local_embedding_model="embedding-768",
        )

        adapters = build_llm_adapters(settings, Metrics(), _no_spend)
        assert isinstance(adapters.analyzer, LocalRequirementAnalyzer)
        assert isinstance(adapters.epic_generator, LocalEpicGenerator)
        assert isinstance(adapters.feature_generator, LocalFeatureGenerator)
        assert isinstance(adapters.story_generator, LocalStoryGenerator)
        assert isinstance(adapters.story_quality_evaluator, LocalStoryQualityEvaluator)
        assert isinstance(adapters.knowledge_embedding, LocalKnowledgeEmbedding)

    def test_openrouter_provider_selects_all_openrouter_adapters(self) -> None:
        settings = Settings(
            llm_provider=LLMProvider.OPENROUTER,
            openrouter_api_key="sk-or-test",
        )

        adapters = build_llm_adapters(settings, Metrics(), _no_spend)

        assert isinstance(adapters.analyzer, OpenRouterRequirementAnalyzer)
        assert isinstance(adapters.epic_generator, OpenRouterEpicGenerator)
        assert isinstance(adapters.feature_generator, OpenRouterFeatureGenerator)
        assert isinstance(adapters.story_generator, OpenRouterStoryGenerator)
        assert isinstance(adapters.story_quality_evaluator, OpenRouterStoryQualityEvaluator)
        assert isinstance(adapters.knowledge_embedding, OpenRouterKnowledgeEmbedding)
        assert isinstance(
            adapters.relationship_classifier,
            OpenRouterRequirementRelationshipClassifier,
        )
        assert isinstance(adapters.answer_suggester, OpenRouterClarificationAnswerSuggester)

    def test_openai_provider_selects_story_quality_evaluator(self) -> None:
        settings = Settings(llm_provider=LLMProvider.OPENAI, openai_api_key="sk-test")

        assert isinstance(
            build_llm_adapters(settings, Metrics(), _no_spend).story_quality_evaluator,
            OpenAIStoryQualityEvaluator,
        )
        assert isinstance(
            build_llm_adapters(settings, Metrics(), _no_spend).knowledge_embedding,
            OpenAIKnowledgeEmbedding,
        )

    def test_each_container_owns_its_own_state(self) -> None:
        """Two containers must not share repositories."""
        first = build_container(Settings(llm_provider=LLMProvider.FAKE))
        second = build_container(Settings(llm_provider=LLMProvider.FAKE))

        assert first.requirement_repository is not second.requirement_repository
        assert first.analysis_repository is not second.analysis_repository

    def test_an_injected_analyzer_wins_over_configuration(self) -> None:
        injected = FakeRequirementAnalyzer()

        container = build_container(
            Settings(llm_provider=LLMProvider.OPENAI, openai_api_key="sk-test"),
            analyzer=injected,
        )

        assert container.analyzer is injected


def test_provider_construction_failure_closes_the_owned_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    client.__enter__.return_value = client

    def close_client(*args: object) -> bool:
        client.close()
        return False

    client.__exit__.side_effect = close_client
    monkeypatch.setattr(composition.httpx, "Client", lambda **kwargs: client)

    def fail_construction(**kwargs: object) -> None:
        raise RuntimeError("adapter construction failed")

    monkeypatch.setattr(composition, "LocalEpicGenerator", fail_construction)
    with pytest.raises(RuntimeError, match="adapter construction failed"):
        build_llm_adapters(
            Settings(
                llm_provider=LLMProvider.LOCAL,
                local_llm_model="test-model",
                local_embedding_model="test-embedding-model",
            ),
            Metrics(),
            _no_spend,
        )
    client.close.assert_called_once()


def test_provider_cleanup_closes_one_shared_client_once(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.__enter__.return_value = client

    def close_client(*args: object) -> bool:
        client.close()
        return False

    client.__exit__.side_effect = close_client
    monkeypatch.setattr(composition.httpx, "Client", lambda **kwargs: client)
    adapters = build_llm_adapters(
        Settings(
            llm_provider=LLMProvider.LOCAL,
            local_llm_model="test-model",
            local_embedding_model="test-embedding-model",
        ),
        Metrics(),
        _no_spend,
    )
    adapters.close()
    adapters.close()
    client.close.assert_called_once()


def test_public_preflight_rejects_fake_identity() -> None:
    from smb_requirement_agent.interfaces.deployment_preflight import validate_public_deployment

    with pytest.raises(ConfigurationError, match="IDENTITY_PROVIDER=oidc"):
        validate_public_deployment(Settings(llm_provider=LLMProvider.FAKE))


def test_database_pool_settings_are_read_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("DATABASE_POOL_MIN_SIZE", "2")
    monkeypatch.setenv("DATABASE_POOL_MAX_SIZE", "7")
    monkeypatch.setenv("DATABASE_POOL_TIMEOUT_SECONDS", "3.5")
    settings = Settings.from_env()
    assert (
        settings.database_pool_min_size,
        settings.database_pool_max_size,
        settings.database_pool_timeout_seconds,
    ) == (2, 7, 3.5)

    with pytest.raises(ConfigurationError, match="DATABASE_POOL_MIN_SIZE"):
        Settings(llm_provider=LLMProvider.FAKE, database_pool_min_size=8, database_pool_max_size=7)
    with pytest.raises(ConfigurationError, match="DATABASE_POOL_MAX_SIZE must be at least 1"):
        Settings(llm_provider=LLMProvider.FAKE, database_pool_min_size=0, database_pool_max_size=0)
    with pytest.raises(ConfigurationError, match="DATABASE_POOL_TIMEOUT_SECONDS"):
        Settings(llm_provider=LLMProvider.FAKE, database_pool_timeout_seconds=0)
    monkeypatch.setenv("DATABASE_POOL_MAX_SIZE", "many")
    with pytest.raises(ConfigurationError, match="DATABASE_POOL_"):
        Settings.from_env()


def test_http_only_api_requires_a_queue_a_separate_worker_can_see(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ConfigurationError, match="API_BACKGROUND_WORKERS=false requires"):
        Settings(llm_provider=LLMProvider.FAKE, api_background_workers=False)
    http_only = Settings(
        llm_provider=LLMProvider.FAKE,
        persistence_provider=PersistenceProvider.POSTGRES,
        database_url="postgresql://example/test",
        api_background_workers=False,
    )
    assert http_only.api_background_workers is False

    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("API_BACKGROUND_WORKERS", "sometimes")
    with pytest.raises(ConfigurationError, match="API_BACKGROUND_WORKERS must be true or false"):
        Settings.from_env()


def test_container_names_every_background_worker_for_readiness() -> None:
    container = build_container(Settings(llm_provider=LLMProvider.FAKE))
    try:
        assert set(container.background_workers) == {
            "requirement_index_worker",
            "workers",
            "attachment_worker",
            "knowledge_event_worker",
            "historic_event_worker",
            "historic_index_worker",
        }
        assert container.background_workers["workers"] is container.ai_job_worker
        # Attachments are this service's only document ingestion; the library left (ADR-0099).
        assert (
            container.background_workers["attachment_worker"]
            is container.attachment_ingestion_worker
        )
    finally:
        container.close_resources()


def test_real_models_poll_architecture_mapping_jobs_in_process() -> None:
    container = build_container(
        Settings(llm_provider=LLMProvider.LOCAL, local_llm_model="m", local_embedding_model="e")
    )
    try:
        # Mapping a Requirement's backlog is queued work; the catalogue's jobs left (ADR-0099).
        assert "architecture_mapping_job_worker" in container.background_workers
        assert "architecture_job_worker" not in container.background_workers
    finally:
        container.close_resources()


class TestOperabilitySettings:
    def test_defaults_log_text_limit_providers_and_export_no_metrics(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        for name in (
            "PROVIDER_RATE_LIMIT_PER_MINUTE",
            "PROVIDER_DAILY_TOKEN_BUDGET",
            "LOG_LEVEL",
            "LOG_FORMAT",
            "METRICS_PORT",
        ):
            monkeypatch.delenv(name, raising=False)

        settings = Settings.from_env()

        assert settings.provider_rate_limit_per_minute == 30
        assert settings.provider_daily_token_budget == 0
        assert settings.log_level == "INFO"
        assert settings.log_format is LogFormat.TEXT
        assert settings.metrics_port is None

    def test_reads_the_operator_choices(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.setenv("PROVIDER_RATE_LIMIT_PER_MINUTE", "0")
        monkeypatch.setenv("PROVIDER_DAILY_TOKEN_BUDGET", "2000000")
        monkeypatch.setenv("LOG_LEVEL", "warning")
        monkeypatch.setenv("LOG_FORMAT", "JSON")
        monkeypatch.setenv("METRICS_PORT", "9464")
        monkeypatch.setenv("METRICS_HOST", "0.0.0.0")

        settings = Settings.from_env()

        assert settings.provider_rate_limit_per_minute == 0
        assert settings.provider_daily_token_budget == 2_000_000
        assert settings.log_level == "WARNING"
        assert settings.log_format is LogFormat.JSON
        assert (settings.metrics_host, settings.metrics_port) == ("0.0.0.0", 9464)

    @pytest.mark.parametrize(
        ("name", "value", "message"),
        [
            ("PROVIDER_RATE_LIMIT_PER_MINUTE", "-1", "PROVIDER_RATE_LIMIT_PER_MINUTE"),
            ("PROVIDER_RATE_LIMIT_PER_MINUTE", "many", "whole numbers"),
            ("PROVIDER_DAILY_TOKEN_BUDGET", "-1", "PROVIDER_DAILY_TOKEN_BUDGET"),
            ("PROVIDER_DAILY_TOKEN_BUDGET", "lots", "whole numbers"),
            ("LOG_LEVEL", "LOUD", "LOG_LEVEL"),
            ("LOG_FORMAT", "xml", "LOG_FORMAT"),
            ("METRICS_PORT", "70000", "METRICS_PORT"),
            ("METRICS_HOST", "  ", "METRICS_HOST"),
            ("REQUEST_MAX_BODY_BYTES", "100", "REQUEST_MAX_BODY_BYTES"),
            ("REQUEST_MAX_BODY_BYTES", "big", "whole numbers"),
        ],
    )
    def test_rejects_invalid_values_at_startup(
        self, monkeypatch: pytest.MonkeyPatch, name: str, value: str, message: str
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.setenv(name, value)

        with pytest.raises(ConfigurationError, match=message):
            Settings.from_env()


class TestKnowledgeService:
    """Where requirement work's knowledge comes from (ADR-0099)."""

    TOKEN = "s" * 40

    @pytest.mark.parametrize(
        ("changes", "message"),
        [
            ({"knowledge_api_base_url": "http://knowledge"}, "set together"),
            ({"requirement_service_token": "s" * 40}, "set together"),
            (
                {"knowledge_api_base_url": "http://knowledge", "requirement_service_token": "x"},
                "REQUIREMENT_SERVICE_TOKEN must be at least 32",
            ),
            (
                {"knowledge_api_base_url": "knowledge:8000", "requirement_service_token": "s" * 40},
                r"http\(s\) URL",
            ),
        ],
    )
    def test_its_settings_are_checked_at_startup(
        self, changes: dict[str, str], message: str
    ) -> None:
        with pytest.raises(ConfigurationError, match=message):
            Settings(llm_provider=LLMProvider.FAKE, **changes)  # type: ignore[arg-type]

    def test_its_settings_are_read_from_the_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.setenv("KNOWLEDGE_API_BASE_URL", "http://knowledge-api:8000")
        monkeypatch.setenv("REQUIREMENT_SERVICE_TOKEN", self.TOKEN)

        settings = Settings.from_env()

        assert settings.knowledge_api_base_url == "http://knowledge-api:8000"
        assert settings.requirement_service_token == self.TOKEN
        assert self.TOKEN not in repr(settings)

    def test_configured_it_answers_over_http(self) -> None:
        from smb_requirement_agent.references.infrastructure.knowledge_client import (
            HttpArchitectureKnowledge,
            HttpKnowledgeViews,
            HttpReferenceKnowledge,
        )

        container = build_container(
            Settings(
                llm_provider=LLMProvider.FAKE,
                knowledge_api_base_url="http://knowledge",
                requirement_service_token=self.TOKEN,
            )
        )
        try:
            assert isinstance(container.knowledge_views._views, HttpKnowledgeViews)
            assert isinstance(container.current_references._knowledge, HttpReferenceKnowledge)
            assert isinstance(container.architecture_knowledge, HttpArchitectureKnowledge)
        finally:
            container.close_resources()

    def test_unconfigured_offline_fakes_answer(self) -> None:
        from smb_requirement_agent.references.infrastructure.knowledge_client import (
            FakeArchitectureKnowledge,
            FakeKnowledgeViews,
            FakeReferenceKnowledge,
        )

        container = build_container(Settings(llm_provider=LLMProvider.FAKE))
        try:
            assert isinstance(container.knowledge_views._views, FakeKnowledgeViews)
            assert isinstance(container.current_references._knowledge, FakeReferenceKnowledge)
            assert isinstance(container.architecture_knowledge, FakeArchitectureKnowledge)
            # The offline feed's one catalogue version is known from the start.
            assert container.current_release.active_release_id() == "offline-catalogue"
        finally:
            container.close_resources()

    def test_production_runs_with_or_without_the_knowledge_portal(self) -> None:
        # ADR-0104: the knowledge portal is an optional link, in production too.
        alone = Settings(**PRODUCTION)  # type: ignore[arg-type]
        assert alone.knowledge_service_url is None
        connected = Settings(
            **PRODUCTION,  # type: ignore[arg-type]
            knowledge_api_base_url="http://knowledge-api:8000",
            requirement_service_token=self.TOKEN,
        )
        assert connected.knowledge_api_base_url == "http://knowledge-api:8000"


# The smallest settings APP_ENV=production accepts.
PRODUCTION: dict[str, object] = {
    "llm_provider": LLMProvider.OPENAI,
    "openai_api_key": "test-only",
    "app_environment": "production",
    "persistence_provider": PersistenceProvider.POSTGRES,
    "database_url": "postgresql://example/test",
    "identity_provider": IdentityProvider.OIDC,
    "oidc_issuer_url": "https://identity.example/tenant",
    "oidc_audience": "api://smb",
    "oidc_client_id": "browser",
    "log_format": LogFormat.JSON,
}


@pytest.mark.parametrize(
    ("override", "named"),
    [
        ({"identity_provider": IdentityProvider.FAKE}, "IDENTITY_PROVIDER=oidc"),
        ({"llm_provider": LLMProvider.FAKE, "openai_api_key": None}, "LLM_PROVIDER=fake"),
        ({"debug_trace_enabled": True}, "DEBUG_TRACE_ENABLED=true"),
        ({"log_format": LogFormat.TEXT}, "LOG_FORMAT=json"),
    ],
)
def test_production_refuses_development_conveniences(
    override: dict[str, object], named: str
) -> None:
    with pytest.raises(ConfigurationError, match=named):
        Settings(**{**PRODUCTION, **override})  # type: ignore[arg-type]


def test_development_keeps_its_conveniences() -> None:
    development = {
        **PRODUCTION,
        "app_environment": "development",
        "identity_provider": IdentityProvider.FAKE,
        "llm_provider": LLMProvider.FAKE,
        "debug_trace_enabled": True,
        "log_format": LogFormat.TEXT,
    }
    assert Settings(**development).app_environment == "development"  # type: ignore[arg-type]


def test_prior_art_is_off_by_default_and_its_caps_are_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    settings = Settings.from_env()
    assert settings.prior_art_enabled is False
    assert (settings.prior_art_judge_calls_per_hour, settings.historic_embed_chunks_per_hour) == (
        60,
        500,
    )
    monkeypatch.setenv("PRIOR_ART_ENABLED", "true")
    monkeypatch.setenv("PRIOR_ART_JUDGE_CALLS_PER_HOUR", "5")
    monkeypatch.setenv("HISTORIC_EMBED_CHUNKS_PER_HOUR", "100")
    settings = Settings.from_env()
    assert settings.prior_art_enabled is True
    assert (settings.prior_art_judge_calls_per_hour, settings.historic_embed_chunks_per_hour) == (
        5,
        100,
    )
    monkeypatch.setenv("PRIOR_ART_ENABLED", "sometimes")
    with pytest.raises(ConfigurationError, match="PRIOR_ART_ENABLED must be true or false"):
        Settings.from_env()
    with pytest.raises(ConfigurationError, match="PRIOR_ART_JUDGE_CALLS_PER_HOUR"):
        Settings(llm_provider=LLMProvider.FAKE, prior_art_judge_calls_per_hour=0)
    with pytest.raises(ConfigurationError, match="HISTORIC_EMBED_CHUNKS_PER_HOUR"):
        Settings(llm_provider=LLMProvider.FAKE, historic_embed_chunks_per_hour=0)
    # Every provider has a prior-art judge.
    container = build_container(Settings(llm_provider=LLMProvider.OPENAI, openai_api_key="sk-x"))
    try:
        assert container.execute_ai_job._screen_prior_art is not None  # noqa: SLF001
    finally:
        container.close_resources()


class TestRenamedAttachmentScanSettings:
    """LIBRARY_* attachment scanning settings became ATTACHMENT_* (ADR-0104)."""

    NAMES = (
        ("ATTACHMENT_SCAN_MODE", "LIBRARY_SCAN_MODE"),
        ("ATTACHMENT_SCANNER_HOST", "LIBRARY_SCANNER_HOST"),
        ("ATTACHMENT_SCANNER_PORT", "LIBRARY_SCANNER_PORT"),
        ("ATTACHMENT_OCR_ARTIFACTS_PATH", "LIBRARY_OCR_ARTIFACTS_PATH"),
    )

    @pytest.fixture(autouse=True)
    def _clean(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        for current, former in self.NAMES:
            monkeypatch.delenv(current, raising=False)
            monkeypatch.delenv(former, raising=False)

    def test_the_new_names_are_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ATTACHMENT_SCANNER_HOST", "scanner")
        monkeypatch.setenv("ATTACHMENT_SCANNER_PORT", "3311")
        monkeypatch.setenv("ATTACHMENT_OCR_ARTIFACTS_PATH", "/var/ocr")

        settings = Settings.from_env()

        assert (settings.library_scanner_host, settings.library_scanner_port) == ("scanner", 3311)
        assert settings.library_ocr_artifacts_path == "/var/ocr"
        assert settings.library_scan_mode == "clamav"

    def test_the_former_names_still_work_for_one_release(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LIBRARY_SCANNER_HOST", "old-scanner")
        monkeypatch.setenv("LIBRARY_SCANNER_PORT", "3312")

        settings = Settings.from_env()

        assert (settings.library_scanner_host, settings.library_scanner_port) == (
            "old-scanner",
            3312,
        )

    def test_both_names_must_agree(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ATTACHMENT_SCANNER_HOST", "scanner")
        monkeypatch.setenv("LIBRARY_SCANNER_HOST", "scanner")
        assert Settings.from_env().library_scanner_host == "scanner"

        monkeypatch.setenv("LIBRARY_SCANNER_HOST", "elsewhere")
        with pytest.raises(ConfigurationError, match="remove LIBRARY_SCANNER_HOST"):
            Settings.from_env()

    def test_errors_name_the_new_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LIBRARY_SCANNER_PORT", "not-a-port")
        with pytest.raises(ConfigurationError, match="ATTACHMENT_SCANNER_PORT must be an integer"):
            Settings.from_env()
