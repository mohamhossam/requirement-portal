"""Application configuration read from the environment.

Configuration is an infrastructure concern: nothing in the domain or the
application layer reads environment variables.  Settings are resolved and
validated once, at startup, so a misconfigured deployment fails loudly on boot
instead of returning a provider error on the first analysis request.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from dotenv import load_dotenv
from smb_kernel.llm.profiles import (
    LLMProfileConfiguration,
    ProfileConfigurationError,
    load_profiles,
)

from smb_requirement_agent.infrastructure.config.options import (
    DEFAULT_AI_JOB_HEARTBEAT_SECONDS,
    DEFAULT_AI_JOB_LEASE_SECONDS,
    DEFAULT_AI_JOB_MAX_ATTEMPTS,
    DEFAULT_AI_JOB_PAYLOAD_RETENTION_DAYS,
    DEFAULT_AI_JOB_POLL_INTERVAL_SECONDS,
    DEFAULT_AI_JOB_RETRY_FIRST_SECONDS,
    DEFAULT_AI_JOB_RETRY_MAX_SECONDS,
    DEFAULT_AI_JOB_SHUTDOWN_GRACE_SECONDS,
    DEFAULT_AI_JOB_WORKER_CONCURRENCY,
    DEFAULT_DATABASE_IDLE_TRANSACTION_TIMEOUT_SECONDS,
    DEFAULT_DATABASE_LOCK_TIMEOUT_SECONDS,
    DEFAULT_DATABASE_POOL_MAX_SIZE,
    DEFAULT_DATABASE_POOL_MIN_SIZE,
    DEFAULT_DATABASE_POOL_TIMEOUT_SECONDS,
    DEFAULT_DATABASE_STATEMENT_TIMEOUT_SECONDS,
    DEFAULT_DEBUG_TRACE_PATH,
    DEFAULT_DOCUMENT_CONTEXT_MAX_CHARACTERS,
    DEFAULT_DOCUMENT_EXTRACTION_CONCURRENCY,
    DEFAULT_DOCUMENT_EXTRACTION_MEMORY_BYTES,
    DEFAULT_DOCUMENT_EXTRACTION_QUEUE,
    DEFAULT_DOCUMENT_EXTRACTION_TIMEOUT_SECONDS,
    DEFAULT_DOCUMENT_MAX_EXTRACTED_CHARACTERS,
    DEFAULT_DOCUMENT_MAX_FILE_BYTES,
    DEFAULT_DOCUMENT_MAX_IMAGE_PIXELS,
    DEFAULT_DOCUMENT_MAX_PDF_PAGES,
    DEFAULT_DOCUMENT_MAX_SPREADSHEET_CELLS,
    DEFAULT_DOCUMENT_MAX_XML_NODES,
    DEFAULT_DOCUMENT_STORAGE_PATH,
    DEFAULT_HISTORIC_EMBED_CHUNKS_PER_HOUR,
    DEFAULT_LOCAL_LLM_BASE_URL,
    DEFAULT_LOCAL_LLM_CONTEXT_WINDOW_TOKENS,
    DEFAULT_LOCAL_LLM_MAX_OUTPUT_TOKENS,
    DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS,
    DEFAULT_NOTIFICATION_RETENTION_DAYS,
    DEFAULT_OIDC_JWKS_TTL_SECONDS,
    DEFAULT_OIDC_LEEWAY_SECONDS,
    DEFAULT_OIDC_UNKNOWN_KEY_CACHE_SIZE,
    DEFAULT_OIDC_UNKNOWN_KEY_TTL_SECONDS,
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    DEFAULT_OPENAI_MAX_OUTPUT_TOKENS,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OPENAI_TIMEOUT_SECONDS,
    DEFAULT_OPENROUTER_BASE_URL,
    DEFAULT_OPENROUTER_DATA_COLLECTION,
    DEFAULT_OPENROUTER_EMBEDDING_MODEL,
    DEFAULT_OPENROUTER_MAX_OUTPUT_TOKENS,
    DEFAULT_OPENROUTER_MODEL,
    DEFAULT_OPENROUTER_TIMEOUT_SECONDS,
    DEFAULT_PRIOR_ART_JUDGE_CALLS_PER_HOUR,
    DEFAULT_PROVIDER_RATE_LIMIT_PER_MINUTE,
    DEFAULT_REQUEST_MAX_BODY_BYTES,
    ConfigurationError,
    IdentityProvider,
    LLMProvider,
    LogFormat,
    PersistenceProvider,
)
from smb_requirement_agent.infrastructure.config.settings_validation import validate_settings

# Attachment scanning settings were named LIBRARY_* while the shared library lived here. The
# old names are read for one more release (ADR-0104); the new name wins when both are set.
RENAMED_SETTINGS = {
    "ATTACHMENT_SCAN_MODE": "LIBRARY_SCAN_MODE",
    "ATTACHMENT_SCANNER_HOST": "LIBRARY_SCANNER_HOST",
    "ATTACHMENT_SCANNER_PORT": "LIBRARY_SCANNER_PORT",
    "ATTACHMENT_OCR_ARTIFACTS_PATH": "LIBRARY_OCR_ARTIFACTS_PATH",
}


def _secret(name: str, environment: Mapping[str, str] = os.environ) -> str | None:
    """A secret from NAME, or from the file NAME_FILE names (Docker or Kubernetes secrets).

    A file keeps the value out of the process environment and `docker inspect`.
    Setting both is refused, so a stale value cannot silently win.
    """
    value = environment.get(name, "").strip()
    path = environment.get(f"{name}_FILE", "").strip()
    if value and path:
        raise ConfigurationError(f"Set {name} or {name}_FILE, not both.")
    if not path:
        return value or None
    try:
        content = Path(path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ConfigurationError(f"{name}_FILE names {path}, which cannot be read.") from exc
    if not content:
        raise ConfigurationError(f"{name}_FILE names {path}, which is empty.")
    return content


class _ProfileEnvironment(dict[str, str]):
    """The environment as model profiles read it: the variable a profile's `api_key_env`
    names may instead come from the file its NAME_FILE names, like every other secret."""

    def get(self, key: str, default: str | None = None) -> str | None:  # type: ignore[override]
        secret = _secret(key, dict(self))
        return default if secret is None else secret


def _database_url() -> str | None:
    """DATABASE_URL, with DATABASE_PASSWORD (or its file) filled in when the URL has none."""
    url = os.getenv("DATABASE_URL", "").strip() or None
    password = _secret("DATABASE_PASSWORD")
    if url is None or password is None:
        return url
    parts = urlsplit(url)
    if parts.password is not None or parts.username is None:
        raise ConfigurationError(
            "DATABASE_PASSWORD needs a DATABASE_URL that names a user and no password."
        )
    host = parts.netloc.rpartition("@")[2]
    netloc = f"{quote(parts.username, safe='')}:{quote(password, safe='')}@{host}"
    return urlunsplit(parts._replace(netloc=netloc))


def _renamed_env(name: str, default: str) -> str:
    """The setting under its current name, else its former one, else the default."""
    value = os.getenv(name)
    if value is not None:
        former = os.getenv(RENAMED_SETTINGS[name])
        if former is not None and former.strip() != value.strip():
            raise ConfigurationError(
                f"{name} and {RENAMED_SETTINGS[name]} disagree; remove {RENAMED_SETTINGS[name]}."
            )
        return value
    return os.getenv(RENAMED_SETTINGS[name], default)


def _attachment_scanner_port() -> int:
    try:
        return int(_renamed_env("ATTACHMENT_SCANNER_PORT", "3310"))
    except ValueError as exc:
        raise ConfigurationError("ATTACHMENT_SCANNER_PORT must be an integer.") from exc


@dataclass(frozen=True)
class PersistenceSettings:
    """Persistence-only configuration for operational database commands."""

    provider: PersistenceProvider = PersistenceProvider.MEMORY
    database_url: str | None = None

    def __post_init__(self) -> None:
        if self.provider is PersistenceProvider.POSTGRES and not self.database_url:
            raise ConfigurationError(
                "PERSISTENCE_PROVIDER=postgres requires DATABASE_URL. Start PostgreSQL and set "
                "DATABASE_URL, or use PERSISTENCE_PROVIDER=memory."
            )

    @classmethod
    def from_env(cls) -> PersistenceSettings:
        """Resolve persistence without validating unrelated provider settings."""
        load_dotenv()
        raw_provider = (
            os.getenv("PERSISTENCE_PROVIDER", PersistenceProvider.MEMORY.value).strip().lower()
        )
        try:
            provider = PersistenceProvider(raw_provider)
        except ValueError as exc:
            supported = ", ".join(sorted(item.value for item in PersistenceProvider))
            raise ConfigurationError(
                f"Unsupported PERSISTENCE_PROVIDER {raw_provider!r}. Supported: {supported}."
            ) from exc
        return cls(
            provider=provider,
            database_url=_database_url(),
        )


@dataclass(frozen=True)
class RetentionSettings:
    """Configuration for the online retention command (ADR-0079)."""

    persistence: PersistenceSettings
    notification_retention_days: int = DEFAULT_NOTIFICATION_RETENTION_DAYS
    # Succeeded and cancelled AI jobs keep their stored inputs this long (ADR-0079 amendment).
    ai_job_payload_retention_days: int = DEFAULT_AI_JOB_PAYLOAD_RETENTION_DAYS

    def __post_init__(self) -> None:
        if self.notification_retention_days < 1:
            raise ConfigurationError(_retention_days_error("NOTIFICATION_RETENTION_DAYS"))
        if self.ai_job_payload_retention_days < 1:
            raise ConfigurationError(_retention_days_error("AI_JOB_PAYLOAD_RETENTION_DAYS"))

    @classmethod
    def from_env(cls) -> RetentionSettings:
        persistence = PersistenceSettings.from_env()
        return cls(
            persistence,
            _retention_days("NOTIFICATION_RETENTION_DAYS", DEFAULT_NOTIFICATION_RETENTION_DAYS),
            _retention_days("AI_JOB_PAYLOAD_RETENTION_DAYS", DEFAULT_AI_JOB_PAYLOAD_RETENTION_DAYS),
        )


def _retention_days_error(name: str) -> str:
    return f"{name} must be a positive whole number of days."


def _retention_days(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError as exc:
        raise ConfigurationError(_retention_days_error(name)) from exc


@dataclass(frozen=True)
class Settings:
    """Resolved runtime configuration."""

    llm_provider: LLMProvider = LLMProvider.OPENAI
    llm_config_path: str | None = None
    llm_profiles: LLMProfileConfiguration | None = field(default=None, repr=False)
    openai_api_key: str | None = None
    openai_model: str = DEFAULT_OPENAI_MODEL
    openai_timeout_seconds: float = DEFAULT_OPENAI_TIMEOUT_SECONDS
    openai_max_output_tokens: int = DEFAULT_OPENAI_MAX_OUTPUT_TOKENS
    openai_embedding_model: str = DEFAULT_OPENAI_EMBEDDING_MODEL
    openrouter_api_key: str | None = field(default=None, repr=False)
    openrouter_model: str = DEFAULT_OPENROUTER_MODEL
    openrouter_embedding_model: str = DEFAULT_OPENROUTER_EMBEDDING_MODEL
    openrouter_base_url: str = DEFAULT_OPENROUTER_BASE_URL
    openrouter_timeout_seconds: float = DEFAULT_OPENROUTER_TIMEOUT_SECONDS
    openrouter_max_output_tokens: int = DEFAULT_OPENROUTER_MAX_OUTPUT_TOKENS
    openrouter_data_collection: str = DEFAULT_OPENROUTER_DATA_COLLECTION
    local_llm_base_url: str = DEFAULT_LOCAL_LLM_BASE_URL
    local_llm_model: str = ""
    local_embedding_model: str = ""
    local_llm_timeout_seconds: float = DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS
    local_llm_reasoning_effort: str | None = None
    local_llm_context_window_tokens: int = DEFAULT_LOCAL_LLM_CONTEXT_WINDOW_TOKENS
    local_llm_max_output_tokens: int = DEFAULT_LOCAL_LLM_MAX_OUTPUT_TOKENS
    local_llm_vision_enabled: bool = False
    persistence_provider: PersistenceProvider = PersistenceProvider.MEMORY
    database_url: str | None = None
    database_pool_min_size: int = DEFAULT_DATABASE_POOL_MIN_SIZE
    database_pool_max_size: int = DEFAULT_DATABASE_POOL_MAX_SIZE
    database_pool_timeout_seconds: float = DEFAULT_DATABASE_POOL_TIMEOUT_SECONDS
    database_statement_timeout_seconds: float = DEFAULT_DATABASE_STATEMENT_TIMEOUT_SECONDS
    database_lock_timeout_seconds: float = DEFAULT_DATABASE_LOCK_TIMEOUT_SECONDS
    database_idle_transaction_timeout_seconds: float = (
        DEFAULT_DATABASE_IDLE_TRANSACTION_TIMEOUT_SECONDS
    )
    api_background_workers: bool = True
    document_max_file_bytes: int = DEFAULT_DOCUMENT_MAX_FILE_BYTES
    document_context_max_characters: int = DEFAULT_DOCUMENT_CONTEXT_MAX_CHARACTERS
    document_extraction_concurrency: int = DEFAULT_DOCUMENT_EXTRACTION_CONCURRENCY
    document_extraction_queue: int = DEFAULT_DOCUMENT_EXTRACTION_QUEUE
    document_extraction_timeout_seconds: float = DEFAULT_DOCUMENT_EXTRACTION_TIMEOUT_SECONDS
    document_extraction_memory_bytes: int = DEFAULT_DOCUMENT_EXTRACTION_MEMORY_BYTES
    document_max_pdf_pages: int = DEFAULT_DOCUMENT_MAX_PDF_PAGES
    document_max_extracted_characters: int = DEFAULT_DOCUMENT_MAX_EXTRACTED_CHARACTERS
    document_max_xml_nodes: int = DEFAULT_DOCUMENT_MAX_XML_NODES
    document_max_image_pixels: int = DEFAULT_DOCUMENT_MAX_IMAGE_PIXELS
    document_max_spreadsheet_cells: int = DEFAULT_DOCUMENT_MAX_SPREADSHEET_CELLS
    document_storage_path: str = DEFAULT_DOCUMENT_STORAGE_PATH
    app_environment: str = "development"
    identity_provider: IdentityProvider = IdentityProvider.FAKE
    oidc_issuer_url: str = ""
    oidc_audience: str = ""
    oidc_client_id: str = ""
    oidc_scopes: str = "openid profile email"
    oidc_company_sso_enabled: bool = True
    oidc_company_sso_alias: str = "company-sso"
    oidc_password_login_enabled: bool = True
    oidc_allowed_algorithms: tuple[str, ...] = ("RS256", "ES256")
    oidc_jwks_ttl_seconds: float = DEFAULT_OIDC_JWKS_TTL_SECONDS
    oidc_unknown_key_ttl_seconds: float = DEFAULT_OIDC_UNKNOWN_KEY_TTL_SECONDS
    oidc_unknown_key_cache_size: int = DEFAULT_OIDC_UNKNOWN_KEY_CACHE_SIZE
    oidc_roles_claim: str = "roles"
    oidc_leeway_seconds: float = DEFAULT_OIDC_LEEWAY_SECONDS
    # Clients besides OIDC_CLIENT_ID whose user tokens are accepted (their `azp`).
    oidc_authorized_parties: tuple[str, ...] = ()
    ai_job_worker_concurrency: int = DEFAULT_AI_JOB_WORKER_CONCURRENCY
    ai_job_poll_interval_seconds: float = DEFAULT_AI_JOB_POLL_INTERVAL_SECONDS
    ai_job_lease_seconds: float = DEFAULT_AI_JOB_LEASE_SECONDS
    ai_job_heartbeat_seconds: float = DEFAULT_AI_JOB_HEARTBEAT_SECONDS
    ai_job_shutdown_grace_seconds: float = DEFAULT_AI_JOB_SHUTDOWN_GRACE_SECONDS
    ai_job_max_attempts: int = DEFAULT_AI_JOB_MAX_ATTEMPTS
    ai_job_retry_first_seconds: float = DEFAULT_AI_JOB_RETRY_FIRST_SECONDS
    ai_job_retry_max_seconds: float = DEFAULT_AI_JOB_RETRY_MAX_SECONDS
    debug_trace_enabled: bool = False
    debug_trace_path: str = DEFAULT_DEBUG_TRACE_PATH
    library_scan_mode: str = "clamav"
    library_scanner_host: str = "127.0.0.1"
    library_scanner_port: int = 3310
    library_ocr_artifacts_path: str = ""
    document_office_preview_executable: str = ""
    provider_rate_limit_per_minute: int = DEFAULT_PROVIDER_RATE_LIMIT_PER_MINUTE
    # Tokens the providers may spend per UTC day across every process; 0 is unlimited.
    provider_daily_token_budget: int = 0
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.TEXT
    metrics_port: int | None = None
    metrics_host: str = "127.0.0.1"
    # An OTLP/HTTP collector's base URL; None leaves tracing off (ADR-0110).
    tracing_endpoint: str | None = None
    tracing_sample_ratio: float = 1.0
    request_max_body_bytes: int = DEFAULT_REQUEST_MAX_BODY_BYTES
    # How the knowledge service proves itself on /internal routes (ADR-0099,
    # ADR-0104): the shared token it presents, and/or its client at the OIDC
    # issuer, whose granted tokens for the audience requirement-internal are
    # admitted. With neither, the internal API is not served at all.
    knowledge_service_token: str | None = field(default=None, repr=False)
    knowledge_service_client_id: str | None = None
    # Where the knowledge service's internal API is, and how this service proves
    # itself there: a shared token, or this service's own client at the OIDC
    # issuer, which then grants it tokens. Unset, offline stand-ins answer for it.
    knowledge_api_base_url: str | None = None
    requirement_service_token: str | None = field(default=None, repr=False)
    requirement_service_client_id: str | None = None
    requirement_service_client_secret: str | None = field(default=None, repr=False)
    # Prior art from historic requirements (Knowledge Center E2, ADR-0102). Off until an
    # operator turns it on, after running the judge's evaluation set against the provider.
    prior_art_enabled: bool = False
    # At most this many prior-art judge calls an hour, across the portal.
    prior_art_judge_calls_per_hour: int = DEFAULT_PRIOR_ART_JUDGE_CALLS_PER_HOUR
    # At most this many historic chunks embedded an hour, per historic requirement.
    historic_embed_chunks_per_hour: int = DEFAULT_HISTORIC_EMBED_CHUNKS_PER_HOUR

    def __post_init__(self) -> None:
        validate_settings(self)

    @property
    def knowledge_service_url(self) -> str | None:
        """The knowledge service this process calls, or None when offline stand-ins answer.

        It is called only with both its address and a way to prove this service
        there: a shared token or this service's client credentials.
        """
        if self.requirement_service_token is None and not self.uses_service_client:
            return None
        return self.knowledge_api_base_url

    @property
    def uses_service_client(self) -> bool:
        """Whether this service asks the OIDC issuer for its tokens to the knowledge service."""
        return (
            self.requirement_service_client_id is not None
            and self.requirement_service_client_secret is not None
        )

    @classmethod
    def from_env(cls, *, config_path: str | None = None) -> Settings:
        """Build settings from the process environment, loading .env if present."""
        load_dotenv()

        llm_config_path = config_path or os.getenv("LLM_CONFIG_PATH", "").strip() or None
        llm_profiles = None
        if llm_config_path:
            try:
                llm_profiles = load_profiles(llm_config_path, _ProfileEnvironment(os.environ))
            except ProfileConfigurationError as exc:
                raise ConfigurationError(str(exc)) from exc
        raw_provider = (
            "profiles"
            if llm_profiles
            else os.getenv("LLM_PROVIDER", LLMProvider.OPENAI.value).strip().lower()
        )
        try:
            provider = LLMProvider(raw_provider)
        except ValueError as exc:
            supported = ", ".join(sorted(p.value for p in LLMProvider))
            raise ConfigurationError(
                f"Unsupported LLM_PROVIDER {raw_provider!r}. Supported values: {supported}."
            ) from exc

        api_key = _secret("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_OPENAI_MODEL
        raw_openai_timeout = os.getenv("OPENAI_TIMEOUT_SECONDS", "").strip()
        try:
            openai_timeout = (
                float(raw_openai_timeout) if raw_openai_timeout else DEFAULT_OPENAI_TIMEOUT_SECONDS
            )
        except ValueError as exc:
            raise ConfigurationError("OPENAI_TIMEOUT_SECONDS must be a number.") from exc
        embedding_model = (
            os.getenv("OPENAI_EMBEDDING_MODEL", "").strip() or DEFAULT_OPENAI_EMBEDDING_MODEL
        )
        openrouter_api_key = _secret("OPENROUTER_API_KEY")
        openrouter_model = os.getenv("OPENROUTER_MODEL", "").strip() or DEFAULT_OPENROUTER_MODEL
        openrouter_embedding_model = (
            os.getenv("OPENROUTER_EMBEDDING_MODEL", "").strip()
            or DEFAULT_OPENROUTER_EMBEDDING_MODEL
        )
        openrouter_base_url = (
            os.getenv("OPENROUTER_BASE_URL", "").strip() or DEFAULT_OPENROUTER_BASE_URL
        )
        raw_openrouter_timeout = os.getenv("OPENROUTER_TIMEOUT_SECONDS", "").strip()
        raw_openrouter_max_output = os.getenv("OPENROUTER_MAX_OUTPUT_TOKENS", "").strip()
        raw_openai_max_output = os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "").strip()
        openrouter_data_collection = (
            os.getenv("OPENROUTER_DATA_COLLECTION", "").strip().lower()
            or DEFAULT_OPENROUTER_DATA_COLLECTION
        )
        local_base_url = os.getenv("LOCAL_LLM_BASE_URL", "").strip() or DEFAULT_LOCAL_LLM_BASE_URL
        local_model = os.getenv("LOCAL_LLM_MODEL", "").strip()
        local_embedding_model = os.getenv("LOCAL_EMBEDDING_MODEL", "").strip()
        raw_local_timeout = os.getenv("LOCAL_LLM_TIMEOUT_SECONDS", "").strip()
        local_reasoning_effort = os.getenv("LOCAL_LLM_REASONING_EFFORT", "").strip() or None
        raw_context_window = os.getenv("LOCAL_LLM_CONTEXT_WINDOW_TOKENS", "").strip()
        raw_max_output = os.getenv("LOCAL_LLM_MAX_OUTPUT_TOKENS", "").strip()
        raw_vision_enabled = os.getenv("LOCAL_LLM_VISION_ENABLED", "false").strip().lower()
        if raw_vision_enabled not in {"true", "false"}:
            raise ConfigurationError("LOCAL_LLM_VISION_ENABLED must be true or false.")
        persistence_settings = PersistenceSettings.from_env()
        raw_document_max = os.getenv("DOCUMENT_MAX_FILE_BYTES", "").strip()
        raw_context_max = os.getenv("DOCUMENT_CONTEXT_MAX_CHARACTERS", "").strip()
        raw_extraction_timeout = os.getenv("DOCUMENT_EXTRACTION_TIMEOUT_SECONDS", "").strip()
        raw_identity = os.getenv("IDENTITY_PROVIDER", IdentityProvider.FAKE.value).strip().lower()
        raw_company_sso_enabled = os.getenv("OIDC_COMPANY_SSO_ENABLED", "true").strip().lower()
        raw_password_login_enabled = (
            os.getenv("OIDC_PASSWORD_LOGIN_ENABLED", "true").strip().lower()
        )
        for name, value in (
            ("OIDC_COMPANY_SSO_ENABLED", raw_company_sso_enabled),
            ("OIDC_PASSWORD_LOGIN_ENABLED", raw_password_login_enabled),
        ):
            if value not in {"true", "false"}:
                raise ConfigurationError(f"{name} must be true or false.")
        raw_job_concurrency = os.getenv("AI_JOB_WORKER_CONCURRENCY", "").strip()
        raw_job_poll = os.getenv("AI_JOB_POLL_INTERVAL_SECONDS", "").strip()
        raw_job_lease = os.getenv("AI_JOB_LEASE_SECONDS", "").strip()
        raw_job_heartbeat = os.getenv("AI_JOB_HEARTBEAT_SECONDS", "").strip()
        raw_job_shutdown_grace = os.getenv("AI_JOB_SHUTDOWN_GRACE_SECONDS", "").strip()
        raw_job_max_attempts = os.getenv("AI_JOB_MAX_ATTEMPTS", "").strip()
        raw_job_retry_first = os.getenv("AI_JOB_RETRY_FIRST_SECONDS", "").strip()
        raw_job_retry_max = os.getenv("AI_JOB_RETRY_MAX_SECONDS", "").strip()
        raw_oidc_jwks_ttl = os.getenv("OIDC_JWKS_TTL_SECONDS", "").strip()
        raw_oidc_unknown_ttl = os.getenv("OIDC_UNKNOWN_KEY_TTL_SECONDS", "").strip()
        raw_oidc_unknown_cache = os.getenv("OIDC_UNKNOWN_KEY_CACHE_SIZE", "").strip()
        raw_oidc_leeway = os.getenv("OIDC_LEEWAY_SECONDS", "").strip()
        raw_debug_trace = os.getenv("DEBUG_TRACE_ENABLED", "false").strip().lower()
        raw_api_workers = os.getenv("API_BACKGROUND_WORKERS", "true").strip().lower()
        raw_pool_min = os.getenv("DATABASE_POOL_MIN_SIZE", "").strip()
        raw_pool_max = os.getenv("DATABASE_POOL_MAX_SIZE", "").strip()
        raw_pool_timeout = os.getenv("DATABASE_POOL_TIMEOUT_SECONDS", "").strip()
        raw_statement_timeout = os.getenv("DATABASE_STATEMENT_TIMEOUT_SECONDS", "").strip()
        raw_lock_timeout = os.getenv("DATABASE_LOCK_TIMEOUT_SECONDS", "").strip()
        raw_idle_transaction_timeout = os.getenv(
            "DATABASE_IDLE_TRANSACTION_TIMEOUT_SECONDS", ""
        ).strip()
        for name, value in (
            ("DEBUG_TRACE_ENABLED", raw_debug_trace),
            ("API_BACKGROUND_WORKERS", raw_api_workers),
        ):
            if value not in {"true", "false"}:
                raise ConfigurationError(f"{name} must be true or false.")
        try:
            identity_provider = IdentityProvider(raw_identity)
        except ValueError as exc:
            supported = ", ".join(item.value for item in IdentityProvider)
            raise ConfigurationError(
                f"Unsupported IDENTITY_PROVIDER {raw_identity!r}. Supported: {supported}."
            ) from exc
        allowed_algorithms = tuple(
            item.strip()
            for item in os.getenv("OIDC_ALLOWED_ALGORITHMS", "RS256,ES256").split(",")
            if item.strip()
        )
        authorized_parties = tuple(
            item.strip()
            for item in os.getenv("OIDC_AUTHORIZED_PARTIES", "").split(",")
            if item.strip()
        )
        try:
            document_max = (
                int(raw_document_max) if raw_document_max else DEFAULT_DOCUMENT_MAX_FILE_BYTES
            )
            document_context_max = (
                int(raw_context_max) if raw_context_max else DEFAULT_DOCUMENT_CONTEXT_MAX_CHARACTERS
            )
            document_extraction_concurrency = int(
                os.getenv("DOCUMENT_EXTRACTION_CONCURRENCY", "")
                or DEFAULT_DOCUMENT_EXTRACTION_CONCURRENCY
            )
            document_extraction_queue = int(
                os.getenv("DOCUMENT_EXTRACTION_QUEUE", "") or DEFAULT_DOCUMENT_EXTRACTION_QUEUE
            )
            document_extraction_memory_bytes = int(
                os.getenv("DOCUMENT_EXTRACTION_MEMORY_BYTES", "")
                or DEFAULT_DOCUMENT_EXTRACTION_MEMORY_BYTES
            )
            document_max_pdf_pages = int(
                os.getenv("DOCUMENT_MAX_PDF_PAGES", "") or DEFAULT_DOCUMENT_MAX_PDF_PAGES
            )
            document_max_extracted_characters = int(
                os.getenv("DOCUMENT_MAX_EXTRACTED_CHARACTERS", "")
                or DEFAULT_DOCUMENT_MAX_EXTRACTED_CHARACTERS
            )
            document_max_xml_nodes = int(
                os.getenv("DOCUMENT_MAX_XML_NODES", "") or DEFAULT_DOCUMENT_MAX_XML_NODES
            )
            document_max_image_pixels = int(
                os.getenv("DOCUMENT_MAX_IMAGE_PIXELS", "") or DEFAULT_DOCUMENT_MAX_IMAGE_PIXELS
            )
            document_max_spreadsheet_cells = int(
                os.getenv("DOCUMENT_MAX_SPREADSHEET_CELLS", "")
                or DEFAULT_DOCUMENT_MAX_SPREADSHEET_CELLS
            )
            document_extraction_timeout = (
                float(raw_extraction_timeout)
                if raw_extraction_timeout
                else DEFAULT_DOCUMENT_EXTRACTION_TIMEOUT_SECONDS
            )
        except ValueError as exc:
            raise ConfigurationError(
                "Document size, complexity, concurrency, and timeout settings must be numeric."
            ) from exc
        try:
            local_timeout = (
                float(raw_local_timeout) if raw_local_timeout else DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS
            )
        except ValueError as exc:
            raise ConfigurationError("LOCAL_LLM_TIMEOUT_SECONDS must be a number.") from exc
        openrouter_timeout = DEFAULT_OPENROUTER_TIMEOUT_SECONDS
        if provider is LLMProvider.OPENROUTER and raw_openrouter_timeout:
            try:
                openrouter_timeout = float(raw_openrouter_timeout)
            except ValueError as exc:
                raise ConfigurationError("OPENROUTER_TIMEOUT_SECONDS must be a number.") from exc
        try:
            context_window = (
                int(raw_context_window)
                if raw_context_window
                else DEFAULT_LOCAL_LLM_CONTEXT_WINDOW_TOKENS
            )
            max_output = (
                int(raw_max_output) if raw_max_output else DEFAULT_LOCAL_LLM_MAX_OUTPUT_TOKENS
            )
        except ValueError as exc:
            raise ConfigurationError(
                "LOCAL_LLM_CONTEXT_WINDOW_TOKENS and LOCAL_LLM_MAX_OUTPUT_TOKENS must be integers."
            ) from exc
        openrouter_max_output = DEFAULT_OPENROUTER_MAX_OUTPUT_TOKENS
        if provider is LLMProvider.OPENROUTER and raw_openrouter_max_output:
            try:
                openrouter_max_output = int(raw_openrouter_max_output)
            except ValueError as exc:
                raise ConfigurationError(
                    "OPENROUTER_MAX_OUTPUT_TOKENS must be an integer."
                ) from exc
        openai_max_output = DEFAULT_OPENAI_MAX_OUTPUT_TOKENS
        if provider is LLMProvider.OPENAI and raw_openai_max_output:
            try:
                openai_max_output = int(raw_openai_max_output)
            except ValueError as exc:
                raise ConfigurationError("OPENAI_MAX_OUTPUT_TOKENS must be an integer.") from exc
        try:
            job_concurrency = (
                int(raw_job_concurrency)
                if raw_job_concurrency
                else DEFAULT_AI_JOB_WORKER_CONCURRENCY
            )
            job_poll = float(raw_job_poll) if raw_job_poll else DEFAULT_AI_JOB_POLL_INTERVAL_SECONDS
            job_lease = float(raw_job_lease) if raw_job_lease else DEFAULT_AI_JOB_LEASE_SECONDS
            job_heartbeat = (
                float(raw_job_heartbeat) if raw_job_heartbeat else DEFAULT_AI_JOB_HEARTBEAT_SECONDS
            )
            job_shutdown_grace = (
                float(raw_job_shutdown_grace)
                if raw_job_shutdown_grace
                else DEFAULT_AI_JOB_SHUTDOWN_GRACE_SECONDS
            )
            job_max_attempts = (
                int(raw_job_max_attempts) if raw_job_max_attempts else DEFAULT_AI_JOB_MAX_ATTEMPTS
            )
            job_retry_first = (
                float(raw_job_retry_first)
                if raw_job_retry_first
                else DEFAULT_AI_JOB_RETRY_FIRST_SECONDS
            )
            job_retry_max = (
                float(raw_job_retry_max) if raw_job_retry_max else DEFAULT_AI_JOB_RETRY_MAX_SECONDS
            )
        except ValueError as exc:
            raise ConfigurationError("AI job worker settings must be numeric.") from exc
        try:
            pool_min = int(raw_pool_min) if raw_pool_min else DEFAULT_DATABASE_POOL_MIN_SIZE
            pool_max = int(raw_pool_max) if raw_pool_max else DEFAULT_DATABASE_POOL_MAX_SIZE
            pool_timeout = (
                float(raw_pool_timeout)
                if raw_pool_timeout
                else DEFAULT_DATABASE_POOL_TIMEOUT_SECONDS
            )
        except ValueError as exc:
            raise ConfigurationError("DATABASE_POOL_* settings must be numeric.") from exc
        try:
            statement_timeout = (
                float(raw_statement_timeout)
                if raw_statement_timeout
                else DEFAULT_DATABASE_STATEMENT_TIMEOUT_SECONDS
            )
            lock_timeout = (
                float(raw_lock_timeout)
                if raw_lock_timeout
                else DEFAULT_DATABASE_LOCK_TIMEOUT_SECONDS
            )
            idle_transaction_timeout = (
                float(raw_idle_transaction_timeout)
                if raw_idle_transaction_timeout
                else DEFAULT_DATABASE_IDLE_TRANSACTION_TIMEOUT_SECONDS
            )
        except ValueError as exc:
            raise ConfigurationError(
                "DATABASE_*_TIMEOUT_SECONDS settings must be numeric."
            ) from exc
        try:
            oidc_jwks_ttl = (
                float(raw_oidc_jwks_ttl) if raw_oidc_jwks_ttl else DEFAULT_OIDC_JWKS_TTL_SECONDS
            )
            oidc_unknown_ttl = (
                float(raw_oidc_unknown_ttl)
                if raw_oidc_unknown_ttl
                else DEFAULT_OIDC_UNKNOWN_KEY_TTL_SECONDS
            )
            oidc_unknown_cache = (
                int(raw_oidc_unknown_cache)
                if raw_oidc_unknown_cache
                else DEFAULT_OIDC_UNKNOWN_KEY_CACHE_SIZE
            )
        except ValueError as exc:
            raise ConfigurationError("OIDC key cache settings must be numeric.") from exc
        try:
            oidc_leeway = float(raw_oidc_leeway) if raw_oidc_leeway else DEFAULT_OIDC_LEEWAY_SECONDS
        except ValueError as exc:
            raise ConfigurationError("OIDC_LEEWAY_SECONDS must be a number.") from exc

        return cls(
            llm_provider=provider,
            llm_config_path=llm_config_path,
            llm_profiles=llm_profiles,
            openai_api_key=api_key,
            openai_model=model,
            openai_timeout_seconds=openai_timeout,
            openai_max_output_tokens=openai_max_output,
            openai_embedding_model=embedding_model,
            openrouter_api_key=openrouter_api_key,
            openrouter_model=openrouter_model,
            openrouter_embedding_model=openrouter_embedding_model,
            openrouter_base_url=openrouter_base_url,
            openrouter_timeout_seconds=openrouter_timeout,
            openrouter_max_output_tokens=openrouter_max_output,
            openrouter_data_collection=openrouter_data_collection,
            local_llm_base_url=local_base_url,
            local_llm_model=local_model,
            local_embedding_model=local_embedding_model,
            local_llm_timeout_seconds=local_timeout,
            local_llm_reasoning_effort=local_reasoning_effort,
            local_llm_context_window_tokens=context_window,
            local_llm_max_output_tokens=max_output,
            local_llm_vision_enabled=raw_vision_enabled == "true",
            persistence_provider=persistence_settings.provider,
            database_url=persistence_settings.database_url,
            database_pool_min_size=pool_min,
            database_pool_max_size=pool_max,
            database_pool_timeout_seconds=pool_timeout,
            database_statement_timeout_seconds=statement_timeout,
            database_lock_timeout_seconds=lock_timeout,
            database_idle_transaction_timeout_seconds=idle_transaction_timeout,
            api_background_workers=raw_api_workers == "true",
            document_max_file_bytes=document_max,
            library_scan_mode=_renamed_env("ATTACHMENT_SCAN_MODE", "clamav").strip(),
            library_ocr_artifacts_path=_renamed_env("ATTACHMENT_OCR_ARTIFACTS_PATH", "").strip(),
            document_office_preview_executable=os.getenv(
                "DOCUMENT_OFFICE_PREVIEW_EXECUTABLE", ""
            ).strip(),
            library_scanner_host=_renamed_env("ATTACHMENT_SCANNER_HOST", "127.0.0.1").strip(),
            library_scanner_port=_attachment_scanner_port(),
            document_context_max_characters=document_context_max,
            document_extraction_concurrency=document_extraction_concurrency,
            document_extraction_queue=document_extraction_queue,
            document_extraction_timeout_seconds=document_extraction_timeout,
            document_extraction_memory_bytes=document_extraction_memory_bytes,
            document_max_pdf_pages=document_max_pdf_pages,
            document_max_extracted_characters=document_max_extracted_characters,
            document_max_xml_nodes=document_max_xml_nodes,
            document_max_image_pixels=document_max_image_pixels,
            document_max_spreadsheet_cells=document_max_spreadsheet_cells,
            document_storage_path=(
                os.getenv("DOCUMENT_STORAGE_PATH", "").strip() or DEFAULT_DOCUMENT_STORAGE_PATH
            ),
            app_environment=os.getenv("APP_ENV", "development").strip().lower(),
            identity_provider=identity_provider,
            oidc_issuer_url=os.getenv("OIDC_ISSUER_URL", "").strip().rstrip("/"),
            oidc_audience=os.getenv("OIDC_AUDIENCE", "").strip(),
            oidc_client_id=os.getenv("OIDC_CLIENT_ID", "").strip(),
            oidc_scopes=os.getenv("OIDC_SCOPES", "").strip() or "openid profile email",
            oidc_company_sso_enabled=raw_company_sso_enabled == "true",
            oidc_company_sso_alias=(
                os.getenv("OIDC_COMPANY_SSO_ALIAS", "").strip() or "company-sso"
            ),
            oidc_password_login_enabled=raw_password_login_enabled == "true",  # noqa: S105 - a flag, not a password
            oidc_allowed_algorithms=allowed_algorithms,
            oidc_jwks_ttl_seconds=oidc_jwks_ttl,
            oidc_unknown_key_ttl_seconds=oidc_unknown_ttl,
            oidc_unknown_key_cache_size=oidc_unknown_cache,
            oidc_roles_claim=os.getenv("OIDC_ROLES_CLAIM", "roles").strip(),
            oidc_leeway_seconds=oidc_leeway,
            oidc_authorized_parties=authorized_parties,
            ai_job_worker_concurrency=job_concurrency,
            ai_job_poll_interval_seconds=job_poll,
            ai_job_lease_seconds=job_lease,
            ai_job_heartbeat_seconds=job_heartbeat,
            ai_job_shutdown_grace_seconds=job_shutdown_grace,
            ai_job_max_attempts=job_max_attempts,
            ai_job_retry_first_seconds=job_retry_first,
            ai_job_retry_max_seconds=job_retry_max,
            debug_trace_enabled=raw_debug_trace == "true",
            debug_trace_path=(
                os.getenv("DEBUG_TRACE_PATH", "").strip() or DEFAULT_DEBUG_TRACE_PATH
            ),
            **_operability_from_env(),
            **_prior_art_from_env(),
        )


def _prior_art_from_env() -> dict[str, Any]:
    """Prior art from historic requirements: an off switch and two hourly caps (ADR-0102)."""
    raw_calls = os.getenv("PRIOR_ART_JUDGE_CALLS_PER_HOUR", "").strip()
    raw_chunks = os.getenv("HISTORIC_EMBED_CHUNKS_PER_HOUR", "").strip()
    try:
        calls = int(raw_calls) if raw_calls else DEFAULT_PRIOR_ART_JUDGE_CALLS_PER_HOUR
        chunks = int(raw_chunks) if raw_chunks else DEFAULT_HISTORIC_EMBED_CHUNKS_PER_HOUR
    except ValueError as exc:
        raise ConfigurationError(
            "PRIOR_ART_JUDGE_CALLS_PER_HOUR and HISTORIC_EMBED_CHUNKS_PER_HOUR must be whole "
            "numbers."
        ) from exc
    raw_enabled = os.getenv("PRIOR_ART_ENABLED", "false").strip().lower()
    if raw_enabled not in {"true", "false"}:
        raise ConfigurationError("PRIOR_ART_ENABLED must be true or false.")
    return {
        "prior_art_enabled": raw_enabled == "true",
        "prior_art_judge_calls_per_hour": calls,
        "historic_embed_chunks_per_hour": chunks,
    }


def _operability_from_env() -> dict[str, Any]:
    """Rate limiting, logging, metrics and tracing: the knobs an operator tunes per deployment."""
    raw_limit = os.getenv("PROVIDER_RATE_LIMIT_PER_MINUTE", "").strip()
    raw_budget = os.getenv("PROVIDER_DAILY_TOKEN_BUDGET", "").strip()
    raw_format = os.getenv("LOG_FORMAT", LogFormat.TEXT.value).strip().lower()
    raw_port = os.getenv("METRICS_PORT", "").strip()
    raw_body = os.getenv("REQUEST_MAX_BODY_BYTES", "").strip()
    raw_ratio = os.getenv("OTEL_TRACES_SAMPLER_ARG", "").strip()
    try:
        ratio = float(raw_ratio) if raw_ratio else 1.0
    except ValueError as exc:
        raise ConfigurationError("OTEL_TRACES_SAMPLER_ARG must be a number from 0 to 1.") from exc
    try:
        limit = int(raw_limit) if raw_limit else DEFAULT_PROVIDER_RATE_LIMIT_PER_MINUTE
        budget = int(raw_budget) if raw_budget else 0
        port = int(raw_port) if raw_port else None
        body = int(raw_body) if raw_body else DEFAULT_REQUEST_MAX_BODY_BYTES
    except ValueError as exc:
        raise ConfigurationError(
            "PROVIDER_RATE_LIMIT_PER_MINUTE, PROVIDER_DAILY_TOKEN_BUDGET, METRICS_PORT and "
            "REQUEST_MAX_BODY_BYTES must be whole numbers."
        ) from exc
    try:
        log_format = LogFormat(raw_format)
    except ValueError as exc:
        raise ConfigurationError("LOG_FORMAT must be text or json.") from exc
    return {
        "provider_rate_limit_per_minute": limit,
        "provider_daily_token_budget": budget,
        "log_level": os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        "log_format": log_format,
        "metrics_port": port,
        "metrics_host": os.getenv("METRICS_HOST", "127.0.0.1").strip(),
        "tracing_endpoint": os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip() or None,
        "tracing_sample_ratio": ratio,
        "request_max_body_bytes": body,
        "knowledge_service_token": _secret("KNOWLEDGE_SERVICE_TOKEN"),
        "knowledge_api_base_url": os.getenv("KNOWLEDGE_API_BASE_URL", "").strip() or None,
        "requirement_service_token": _secret("REQUIREMENT_SERVICE_TOKEN"),
        "knowledge_service_client_id": (
            os.getenv("KNOWLEDGE_SERVICE_CLIENT_ID", "").strip() or None
        ),
        "requirement_service_client_id": (
            os.getenv("REQUIREMENT_SERVICE_CLIENT_ID", "").strip() or None
        ),
        "requirement_service_client_secret": _secret("REQUIREMENT_SERVICE_CLIENT_SECRET"),
    }
