"""Operational entry points built from the same adapters as the application.

Maintenance, model qualification and smoke checks run outside the API
lifecycle; they live beside the composition root, not inside it."""

from __future__ import annotations

import io
from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic

import httpx as httpx
from PIL import Image
from pydantic import BaseModel, Field
from smb_kernel.diagnostics import build_debug_trace
from smb_kernel.llm.compatible_transport import (
    CompatibleStructuredOutputClient,
    ConfiguredKnowledgeEmbedding,
    GoogleEmbeddingTokenCounter,
)
from smb_kernel.persistence.connector import (
    DirectPostgresConnector,
)
from smb_kernel.time.system import SystemClock

from smb_requirement_agent.application.errors import ModelTransportError
from smb_requirement_agent.governance.infrastructure.postgres_revisions import (
    PostgresRevisionRepository,
    PostgresRevisionWriter,
)
from smb_requirement_agent.infrastructure.config.options import ConfigurationError
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence.postgres_session import (
    PostgresCommitSession,
)
from smb_requirement_agent.infrastructure.persistence.postgres_store import PostgresStore
from smb_requirement_agent.interfaces.api.composition.projections import (
    refresh_postgres_projections,
)
from smb_requirement_agent.jobs.application.use_cases.retention import PruneReadNotifications
from smb_requirement_agent.jobs.infrastructure.postgres_ai_jobs import (
    PostgresNotificationRepository,
)
from smb_requirement_agent.knowledge.infrastructure.source_dependencies import (
    PostgresSourceDependencies,
)
from smb_requirement_agent.references.application.use_cases.qualify_chunk_tokens import (
    qualify_chunk_tokens,
)
from smb_requirement_agent.reporting.application.use_cases.dependency_projection import (
    DependencyProjection,
)
from smb_requirement_agent.reporting.infrastructure.postgres_snapshots import (
    PostgresSnapshotReader,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


def build_notification_retention(database_url: str) -> PruneReadNotifications:
    """Build the online retention path using persistence adapters only."""
    store = PostgresStore(
        DirectPostgresConnector(database_url),
        PostgresRevisionWriter().capture,
        refresh_postgres_projections,
    )
    return PruneReadNotifications(PostgresNotificationRepository(store), SystemClock())


def build_projection_rebuild(database_url: str) -> Callable[[], int]:
    """Build the maintenance path using persistence adapters only."""

    store = PostgresStore(
        DirectPostgresConnector(database_url),
        PostgresRevisionWriter().capture,
        refresh_postgres_projections,
    )

    def rebuild() -> int:
        cursor = ""
        count = 0
        with store.connection() as connection:
            connection.execute(
                "DELETE FROM maintenance_markers WHERE name=%s", ("activity-worklist-v2",)
            )
        while True:
            with store.connection() as connection:
                rows = connection.execute(
                    "SELECT requirement_id FROM requirements WHERE requirement_id > %s "
                    "ORDER BY requirement_id LIMIT 200",
                    (cursor,),
                ).fetchall()
            if not rows:
                break
            for row in rows:
                requirement_id = RequirementId(str(row[0]))
                with store.transaction():
                    store.lock_requirement(requirement_id)
                    with store.connection() as connection:
                        connection.execute(
                            "DELETE FROM activity_projection_cursors WHERE requirement_id=%s",
                            (requirement_id.value,),
                        )
                        connection.execute(
                            "DELETE FROM activity_input_cursors WHERE requirement_id=%s",
                            (requirement_id.value,),
                        )
                        connection.execute(
                            "DELETE FROM activity_event_projection WHERE requirement_id=%s",
                            (requirement_id.value,),
                        )
                    with store.connection() as connection:
                        refresh_postgres_projections(connection, (requirement_id,))
                        session = PostgresCommitSession(connection)
                        DependencyProjection(
                            PostgresSnapshotReader(session), PostgresSourceDependencies(session)
                        ).backfill(requirement_id, PostgresRevisionRepository(session))
                cursor = requirement_id.value
                count += 1
        with store.connection() as connection:
            connection.execute(
                "INSERT INTO maintenance_markers (name) VALUES (%s) "
                "ON CONFLICT (name) DO UPDATE SET completed_at=now()",
                ("activity-worklist-v2",),
            )
        return count

    return rebuild


def qualify_embedding_tokens(
    settings: Settings,
    samples: tuple[tuple[str, str], ...],
    input_limit: int,
) -> dict[str, object]:
    """Explicit synthetic qualification; providers are wired only here."""

    config = settings.llm_profiles
    if config is None:
        raise ConfigurationError("Token qualification requires an explicit embedding profile.")
    trace = build_debug_trace(enabled=False, path=settings.debug_trace_path, secrets=config.secrets)
    try:
        with httpx.Client() as http:
            counter = GoogleEmbeddingTokenCounter(config.selected_embedding, http, trace)
            result = qualify_chunk_tokens(counter, samples, input_limit)
            if result["all_within_model_limit"]:
                vectors = ConfiguredKnowledgeEmbedding(
                    config.selected_embedding, http, trace
                ).embed(
                    tuple(text for _, text in samples),
                )
                result["embedding_requests_accepted"] = len(vectors) == len(samples)
            else:
                result["embedding_requests_accepted"] = False
            result["measured_at"] = datetime.now(UTC).isoformat()
            result["model"] = config.selected_embedding.model
            result["endpoint"] = config.selected_embedding.endpoint
            return result
    finally:
        trace.close()


def smoke_llm_profiles(settings: Settings) -> dict[str, object]:
    """Explicit synthetic live checks; composition root owns all transport construction."""

    class SmokeResponse(BaseModel):
        answer: str = Field(min_length=1)

    config = settings.llm_profiles
    if config is None:
        raise ConfigurationError("Live profile checks require LLM_CONFIG_PATH.")
    trace = build_debug_trace(
        enabled=settings.debug_trace_enabled, path=settings.debug_trace_path, secrets=config.secrets
    )
    results: dict[str, object] = {}
    try:
        with httpx.Client() as http:
            seen: set[str] = set()
            for task in ("analysis", "generation", "review", "knowledge"):
                profile = config.for_task(task)
                if profile.fingerprint in seen:
                    continue
                client = CompatibleStructuredOutputClient(profile, http, trace)
                start = monotonic()
                text = client.parse(
                    system_prompt="Return the requested answer using the supplied schema.",
                    user_prompt="Set answer to exactly 'structured text works'.",
                    schema_type=SmokeResponse,
                )
                if text.answer.strip() != "structured text works":
                    raise ModelTransportError("invalid_output")
                results[task] = {
                    "model": profile.model,
                    "text": "passed",
                    "duration_seconds": round(monotonic() - start, 2),
                }
                seen.add(profile.fingerprint)
            analysis = config.for_task("analysis")
            stream = io.BytesIO()
            Image.new("RGB", (32, 32), "blue").save(stream, format="PNG")
            visual = CompatibleStructuredOutputClient(analysis, http, trace).parse(
                system_prompt="Describe the supplied image using the schema.",
                user_prompt="Set answer to the main color only, in lowercase.",
                images=(("image/png", stream.getvalue()),),
                schema_type=SmokeResponse,
            )
            if "blue" not in visual.answer.casefold():
                raise ModelTransportError("invalid_output")
            results["image"] = "passed"
            vectors = ConfiguredKnowledgeEmbedding(config.selected_embedding, http, trace).embed(
                ("Business customers can check broadband coverage.", "Orders require an address.")
            )
            results["embeddings"] = {
                "count": len(vectors),
                "dimensions": len(vectors[0]),
                "identity": config.selected_embedding.identity,
            }
    finally:
        trace.close()
    return results
