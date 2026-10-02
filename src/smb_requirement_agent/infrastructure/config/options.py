"""Configuration vocabulary: selectable providers, documented defaults, the error.

No environment access here; settings.py alone reads the environment.
"""

from __future__ import annotations

from enum import Enum

DEFAULT_OPENAI_MODEL = "gpt-4o"


DEFAULT_OPENAI_TIMEOUT_SECONDS = 60.0


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


DEFAULT_AI_JOB_POLL_INTERVAL_SECONDS = 1.0


DEFAULT_AI_JOB_LEASE_SECONDS = 90.0


DEFAULT_AI_JOB_HEARTBEAT_SECONDS = 20.0


DEFAULT_AI_JOB_SHUTDOWN_GRACE_SECONDS = 150.0


DEFAULT_OIDC_JWKS_TTL_SECONDS = 900.0


DEFAULT_OIDC_UNKNOWN_KEY_TTL_SECONDS = 30.0


DEFAULT_OIDC_UNKNOWN_KEY_CACHE_SIZE = 256


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


class LogFormat(Enum):
    """Operational log output: readable lines locally, one JSON object per line in production."""

    TEXT = "text"
    JSON = "json"


LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


DEFAULT_PROVIDER_RATE_LIMIT_PER_MINUTE = 30
# Read notifications older than this are pruned by the retention command (ADR-0079).
DEFAULT_NOTIFICATION_RETENTION_DAYS = 90


DEFAULT_REQUEST_MAX_BODY_BYTES = 2 * 1024 * 1024
