"""Configuration vocabulary: selectable providers, documented defaults, the error.

No environment access here; settings.py alone reads the environment.
"""

from __future__ import annotations

from enum import Enum

from smb_kernel.observability.logging import LogFormat as LogFormat

DEFAULT_OPENAI_MODEL = "gpt-4o"


DEFAULT_OPENAI_TIMEOUT_SECONDS = 60.0


# Cap on each OpenAI reply, sent as max_completion_tokens; matches OpenRouter's.
DEFAULT_OPENAI_MAX_OUTPUT_TOKENS = 8192


DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"


DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


DEFAULT_OPENROUTER_MODEL = "google/gemma-4-31b-it:free"


DEFAULT_OPENROUTER_EMBEDDING_MODEL = "openai/text-embedding-3-small"


DEFAULT_OPENROUTER_TIMEOUT_SECONDS = 120.0


DEFAULT_OPENROUTER_MAX_OUTPUT_TOKENS = 8192


DEFAULT_OPENROUTER_DATA_COLLECTION = "deny"


DEFAULT_LOCAL_LLM_BASE_URL = "http://127.0.0.1:1234/v1"


DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS = 120.0


DEFAULT_LOCAL_LLM_CONTEXT_WINDOW_TOKENS = 8192


DEFAULT_LOCAL_LLM_MAX_OUTPUT_TOKENS = 4096


DEFAULT_DOCUMENT_MAX_FILE_BYTES = 10 * 1024 * 1024


DEFAULT_DOCUMENT_CONTEXT_MAX_CHARACTERS = 60_000


DEFAULT_DOCUMENT_EXTRACTION_CONCURRENCY = 2


DEFAULT_DOCUMENT_EXTRACTION_QUEUE = 4


DEFAULT_DOCUMENT_EXTRACTION_TIMEOUT_SECONDS = 30.0


DEFAULT_DOCUMENT_EXTRACTION_MEMORY_BYTES = 512 * 1024 * 1024


DEFAULT_DOCUMENT_MAX_PDF_PAGES = 200


DEFAULT_DOCUMENT_MAX_EXTRACTED_CHARACTERS = 1_000_000


DEFAULT_DOCUMENT_MAX_XML_NODES = 250_000


DEFAULT_DOCUMENT_MAX_IMAGE_PIXELS = 20_000_000


DEFAULT_DOCUMENT_MAX_SPREADSHEET_CELLS = 1_000_000


DEFAULT_DOCUMENT_STORAGE_PATH = ".data/documents"


DEFAULT_AI_JOB_WORKER_CONCURRENCY = 1


DEFAULT_DATABASE_POOL_MIN_SIZE = 1


DEFAULT_DATABASE_POOL_MAX_SIZE = 20


DEFAULT_DATABASE_POOL_TIMEOUT_SECONDS = 10.0


# Session limits on every pooled connection (production hardening PR 3). One-shot commands
# (migrate, maintenance, retention) use direct connections without them.
DEFAULT_DATABASE_STATEMENT_TIMEOUT_SECONDS = 30.0
DEFAULT_DATABASE_LOCK_TIMEOUT_SECONDS = 5.0
DEFAULT_DATABASE_IDLE_TRANSACTION_TIMEOUT_SECONDS = 60.0


DEFAULT_AI_JOB_POLL_INTERVAL_SECONDS = 1.0


DEFAULT_AI_JOB_LEASE_SECONDS = 90.0


DEFAULT_AI_JOB_HEARTBEAT_SECONDS = 20.0


DEFAULT_AI_JOB_SHUTDOWN_GRACE_SECONDS = 150.0


# Attempts a job may start before it fails as attempts_exhausted (ADR-0020 amendment).
DEFAULT_AI_JOB_MAX_ATTEMPTS = 3
# Backoff before a job that met a transient provider or platform outage runs again: the
# first wait, doubled per attempt up to the longest (ADR-0020 amendment, retry with backoff).
DEFAULT_AI_JOB_RETRY_FIRST_SECONDS = 30.0
DEFAULT_AI_JOB_RETRY_MAX_SECONDS = 300.0


DEFAULT_OIDC_JWKS_TTL_SECONDS = 900.0


DEFAULT_OIDC_UNKNOWN_KEY_TTL_SECONDS = 30.0


DEFAULT_OIDC_UNKNOWN_KEY_CACHE_SIZE = 256


# Clock difference allowed with the issuer on a token's exp, nbf and iat.
DEFAULT_OIDC_LEEWAY_SECONDS = 60.0


DEFAULT_DEBUG_TRACE_PATH = "logs/debug.log"


SUPPORTED_LOCAL_REASONING_EFFORTS = {"none", "low", "medium", "high"}


SUPPORTED_OPENROUTER_DATA_COLLECTION = {"deny"}


SUPPORTED_OIDC_ALGORITHMS = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
    }
)


class ConfigurationError(Exception):
    """Raised when the environment does not describe a runnable configuration."""


class LLMProvider(Enum):
    """Selectable requirement-analyzer backends."""

    PROFILES = "profiles"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    FAKE = "fake"
    LOCAL = "local"


class PersistenceProvider(Enum):
    """Selectable persistence adapters."""

    MEMORY = "memory"
    POSTGRES = "postgres"


class IdentityProvider(Enum):
    FAKE = "fake"
    OIDC = "oidc"


LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


DEFAULT_PROVIDER_RATE_LIMIT_PER_MINUTE = 30
# Prior art from historic requirements (Knowledge Center E2): judge calls an hour across the
# portal, and historic chunks embedded an hour per historic requirement.
DEFAULT_PRIOR_ART_JUDGE_CALLS_PER_HOUR = 60
DEFAULT_HISTORIC_EMBED_CHUNKS_PER_HOUR = 500
# Read notifications older than this are pruned by the retention command (ADR-0079).
DEFAULT_NOTIFICATION_RETENTION_DAYS = 90
# Finished AI jobs' stored inputs are cleared after this many days (ADR-0079 amendment).
DEFAULT_AI_JOB_PAYLOAD_RETENTION_DAYS = 90


DEFAULT_REQUEST_MAX_BODY_BYTES = 2 * 1024 * 1024


class AdoPublisher(Enum):
    """Where approved backlogs are published (Slice 12)."""

    # Publication is offered nowhere; the preview says it is not set up.
    NONE = "none"
    # An in-memory stand-in, for running the flow with no Azure DevOps account.
    FAKE = "fake"
    AZURE_DEVOPS = "azure_devops"


DEFAULT_ADO_TIMEOUT_SECONDS = 30.0
