"""Cross-field validation of resolved settings.

Runs once, when `Settings` is constructed, so a bad combination fails the boot
naming the variables involved. It reads only the resolved values; settings.py
alone reads the environment (AGENTS.md section 4.5).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from smb_requirement_agent.infrastructure.config.options import (
    LOG_LEVELS,
    SUPPORTED_LOCAL_REASONING_EFFORTS,
    SUPPORTED_OIDC_ALGORITHMS,
    SUPPORTED_OPENROUTER_DATA_COLLECTION,
    ConfigurationError,
    IdentityProvider,
    LLMProvider,
    PersistenceProvider,
)

if TYPE_CHECKING:
    from smb_requirement_agent.infrastructure.config.settings import Settings


def validate_settings(settings: Settings) -> None:
    if settings.request_max_body_bytes < 1024:
        raise ConfigurationError("REQUEST_MAX_BODY_BYTES must be at least 1024.")
    if settings.provider_rate_limit_per_minute < 0:
        raise ConfigurationError(
            "PROVIDER_RATE_LIMIT_PER_MINUTE must be 0 (unlimited) or a positive number."
        )
    if settings.log_level not in LOG_LEVELS:
        raise ConfigurationError(f"LOG_LEVEL must be one of {', '.join(LOG_LEVELS)}.")
    if settings.metrics_port is not None and not 1 <= settings.metrics_port <= 65535:
        raise ConfigurationError("METRICS_PORT must be a TCP port between 1 and 65535.")
    if not settings.metrics_host.strip():
        raise ConfigurationError("METRICS_HOST must not be blank.")
    if settings.library_scan_mode not in {"clamav", "offline"}:
        raise ConfigurationError("LIBRARY_SCAN_MODE must be clamav or offline.")
    if settings.library_scan_mode == "offline" and (
        settings.persistence_provider is not PersistenceProvider.MEMORY
        or settings.identity_provider is not IdentityProvider.FAKE
    ):
        raise ConfigurationError(
            "LIBRARY_SCAN_MODE=offline requires memory persistence and fake identity."
        )
    if not settings.library_scanner_host.strip() or not 1 <= settings.library_scanner_port <= 65535:
        raise ConfigurationError("Library scanner host and port are invalid.")
    if settings.llm_provider is LLMProvider.PROFILES and settings.llm_profiles is None:
        raise ConfigurationError("LLM_PROVIDER=profiles requires LLM_CONFIG_PATH.")
    if settings.llm_provider is LLMProvider.OPENAI and not settings.openai_api_key:
        raise ConfigurationError(
            "LLM_PROVIDER=openai requires OPENAI_API_KEY to be set. "
            "Set LLM_PROVIDER=fake to run without a provider account."
        )
    if settings.llm_provider is LLMProvider.OPENROUTER:
        if not settings.openrouter_api_key or not settings.openrouter_api_key.strip():
            raise ConfigurationError(
                "LLM_PROVIDER=openrouter requires OPENROUTER_API_KEY to be set. "
                "Set LLM_PROVIDER=fake to run without a provider account."
            )
        if not settings.openrouter_model.strip():
            raise ConfigurationError("OPENROUTER_MODEL must not be blank.")
        if not settings.openrouter_embedding_model.strip():
            raise ConfigurationError("OPENROUTER_EMBEDDING_MODEL must not be blank.")
        parsed_openrouter_url = urlsplit(settings.openrouter_base_url)
        if parsed_openrouter_url.scheme != "https" or not parsed_openrouter_url.netloc:
            raise ConfigurationError(
                "OPENROUTER_BASE_URL must be an absolute HTTPS API root, for example "
                "https://openrouter.ai/api/v1."
            )
        if settings.openrouter_timeout_seconds <= 0:
            raise ConfigurationError("OPENROUTER_TIMEOUT_SECONDS must be greater than zero.")
        if settings.openrouter_max_output_tokens < 1:
            raise ConfigurationError("OPENROUTER_MAX_OUTPUT_TOKENS must be positive.")
        if settings.openrouter_data_collection not in SUPPORTED_OPENROUTER_DATA_COLLECTION:
            supported = ", ".join(sorted(SUPPORTED_OPENROUTER_DATA_COLLECTION))
            raise ConfigurationError(f"OPENROUTER_DATA_COLLECTION must be one of: {supported}.")
    if settings.llm_provider is LLMProvider.LOCAL:
        if not settings.local_llm_model.strip():
            raise ConfigurationError(
                "LLM_PROVIDER=local requires LOCAL_LLM_MODEL to be set to the model "
                "identifier loaded by the local server."
            )
        if not settings.local_embedding_model.strip():
            raise ConfigurationError(
                "LLM_PROVIDER=local requires LOCAL_EMBEDDING_MODEL to be set to a "
                "768-dimensional embedding model served by the local endpoint."
            )
        parsed_url = urlsplit(settings.local_llm_base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ConfigurationError(
                "LOCAL_LLM_BASE_URL must be an absolute http(s) URL ending at the "
                "OpenAI-compatible API root, for example http://127.0.0.1:1234/v1."
            )
        if settings.local_llm_timeout_seconds <= 0:
            raise ConfigurationError("LOCAL_LLM_TIMEOUT_SECONDS must be greater than zero.")
        if (
            settings.local_llm_reasoning_effort is not None
            and settings.local_llm_reasoning_effort not in SUPPORTED_LOCAL_REASONING_EFFORTS
        ):
            supported = ", ".join(sorted(SUPPORTED_LOCAL_REASONING_EFFORTS))
            raise ConfigurationError(
                f"LOCAL_LLM_REASONING_EFFORT must be empty or one of: {supported}."
            )
        if settings.local_llm_context_window_tokens < 1024:
            raise ConfigurationError("LOCAL_LLM_CONTEXT_WINDOW_TOKENS must be at least 1024.")
        if not 1 <= settings.local_llm_max_output_tokens < settings.local_llm_context_window_tokens:
            raise ConfigurationError(
                "LOCAL_LLM_MAX_OUTPUT_TOKENS must be positive and smaller than "
                "LOCAL_LLM_CONTEXT_WINDOW_TOKENS."
            )
    if settings.persistence_provider is PersistenceProvider.POSTGRES and not settings.database_url:
        raise ConfigurationError(
            "PERSISTENCE_PROVIDER=postgres requires DATABASE_URL. Start PostgreSQL and set "
            "DATABASE_URL, or use PERSISTENCE_PROVIDER=memory."
        )
    if settings.app_environment not in {"development", "test", "production"}:
        raise ConfigurationError("APP_ENV must be development, test, or production.")
    if (
        settings.app_environment == "production"
        and settings.persistence_provider is not PersistenceProvider.POSTGRES
    ):
        raise ConfigurationError("APP_ENV=production requires PERSISTENCE_PROVIDER=postgres.")
    if settings.document_max_file_bytes < 1:
        raise ConfigurationError("DOCUMENT_MAX_FILE_BYTES must be positive.")
    if settings.document_context_max_characters < 1:
        raise ConfigurationError("DOCUMENT_CONTEXT_MAX_CHARACTERS must be positive.")
    extraction_values = (
        settings.document_extraction_concurrency,
        settings.document_extraction_queue,
        settings.document_extraction_timeout_seconds,
        settings.document_extraction_memory_bytes,
        settings.document_max_pdf_pages,
        settings.document_max_extracted_characters,
        settings.document_max_xml_nodes,
        settings.document_max_image_pixels,
        settings.document_max_spreadsheet_cells,
    )
    if any(value <= 0 for value in extraction_values):
        raise ConfigurationError("Document extraction limits must all be positive.")
    if not settings.document_storage_path.strip():
        raise ConfigurationError("DOCUMENT_STORAGE_PATH must not be blank.")
    if settings.identity_provider is IdentityProvider.OIDC:
        for name, value in (
            ("OIDC_ISSUER_URL", settings.oidc_issuer_url),
            ("OIDC_AUDIENCE", settings.oidc_audience),
            ("OIDC_CLIENT_ID", settings.oidc_client_id),
        ):
            if not value.strip():
                raise ConfigurationError(f"IDENTITY_PROVIDER=oidc requires {name}.")
        parsed_issuer = urlsplit(settings.oidc_issuer_url)
        if parsed_issuer.scheme != "https" or not parsed_issuer.netloc:
            raise ConfigurationError("OIDC_ISSUER_URL must be an absolute HTTPS URL.")
        if not settings.oidc_allowed_algorithms or any(
            item not in SUPPORTED_OIDC_ALGORITHMS for item in settings.oidc_allowed_algorithms
        ):
            raise ConfigurationError(
                "OIDC_ALLOWED_ALGORITHMS must contain supported asymmetric JWT algorithms only."
            )
        if settings.oidc_jwks_ttl_seconds <= 0 or settings.oidc_unknown_key_ttl_seconds <= 0:
            raise ConfigurationError("OIDC key cache TTL values must be greater than zero.")
        if settings.oidc_unknown_key_cache_size < 1:
            raise ConfigurationError("OIDC_UNKNOWN_KEY_CACHE_SIZE must be at least 1.")
        if not settings.oidc_company_sso_enabled and not settings.oidc_password_login_enabled:
            raise ConfigurationError("At least one OIDC login choice must be enabled.")
        if settings.oidc_company_sso_enabled and not settings.oidc_company_sso_alias.strip():
            raise ConfigurationError(
                "OIDC_COMPANY_SSO_ALIAS must not be blank when company SSO is enabled."
            )
        if not settings.oidc_roles_claim.strip():
            raise ConfigurationError("OIDC_ROLES_CLAIM must not be blank.")
    if (
        settings.app_environment == "production"
        and settings.identity_provider is IdentityProvider.FAKE
    ):
        raise ConfigurationError("APP_ENV=production requires IDENTITY_PROVIDER=oidc.")
    if settings.app_environment == "production" and not settings.knowledge_evaluation_approved:
        raise ConfigurationError(
            "Production architecture mapping requires KNOWLEDGE_EVALUATION_APPROVED=true "
            "after the bilingual architecture evaluation passes on the configured models."
        )
    if not 0 <= settings.database_pool_min_size <= settings.database_pool_max_size:
        raise ConfigurationError(
            "DATABASE_POOL_MIN_SIZE must be between 0 and DATABASE_POOL_MAX_SIZE."
        )
    if settings.database_pool_max_size < 1:
        raise ConfigurationError("DATABASE_POOL_MAX_SIZE must be at least 1.")
    if settings.database_pool_timeout_seconds <= 0:
        raise ConfigurationError("DATABASE_POOL_TIMEOUT_SECONDS must be greater than zero.")
    if (
        not settings.api_background_workers
        and settings.persistence_provider is PersistenceProvider.MEMORY
    ):
        # A separate worker process cannot see this process's in-memory queues.
        raise ConfigurationError(
            "API_BACKGROUND_WORKERS=false requires PERSISTENCE_PROVIDER=postgres so a "
            "separate worker process can claim queued jobs."
        )
    if settings.openai_timeout_seconds <= 0:
        raise ConfigurationError("OPENAI_TIMEOUT_SECONDS must be greater than zero.")
    if settings.ai_job_worker_concurrency < 1:
        raise ConfigurationError("AI_JOB_WORKER_CONCURRENCY must be at least 1.")
    if settings.ai_job_poll_interval_seconds <= 0:
        raise ConfigurationError("AI_JOB_POLL_INTERVAL_SECONDS must be greater than zero.")
    if settings.ai_job_lease_seconds <= 0 or settings.ai_job_heartbeat_seconds <= 0:
        raise ConfigurationError(
            "AI_JOB_LEASE_SECONDS and AI_JOB_HEARTBEAT_SECONDS must be greater than zero."
        )
    if settings.ai_job_heartbeat_seconds * 2 >= settings.ai_job_lease_seconds:
        raise ConfigurationError(
            "AI_JOB_HEARTBEAT_SECONDS must be less than half AI_JOB_LEASE_SECONDS."
        )
    if settings.ai_job_shutdown_grace_seconds <= 0:
        raise ConfigurationError("AI_JOB_SHUTDOWN_GRACE_SECONDS must be greater than zero.")
    if settings.debug_trace_enabled and not settings.debug_trace_path.strip():
        raise ConfigurationError(
            "DEBUG_TRACE_PATH must not be blank when DEBUG_TRACE_ENABLED=true."
        )
