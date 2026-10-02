"""Requirement work's adapters onto the knowledge service's internal API (ADR-0099).

Each decodes the response into this application's own contract values and
fails as `ServiceUnavailableError` when it cannot: a malformed answer never
reaches the domain, and never leaks as a `KeyError` or `ValidationError`.
The fakes are deterministic stand-ins for running without the knowledge service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import TypeAdapter
from smb_kernel.errors import ServiceUnavailableError
from smb_kernel.http.client import InternalHttpClient

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureQuery,
)
from smb_requirement_agent.application.ports.knowledge_events import KnowledgeEvent
from smb_requirement_agent.application.ports.reference_grounding import ReferenceEvidence

_QUERY = TypeAdapter(ArchitectureQuery)
_MATCH = TypeAdapter(ArchitectureKnowledgeMatch)
_EVIDENCE = TypeAdapter(tuple[ReferenceEvidence, ...])


def _decode[T](adapter: TypeAdapter[T], body: Any, what: str) -> T:
    """Decode a response into contract values, whose constructors check their invariants.

    The boundary for an unusable answer: whatever a constructor raises (a
    validation error, or a domain invariant error pydantic passes through)
    becomes one explicit adapter failure (AGENTS.md section 4.3).
    """
    try:
        return adapter.validate_python(body)
    except Exception as exc:
        raise ServiceUnavailableError(f"The knowledge service returned unusable {what}.") from exc


class HttpArchitectureKnowledge:
    def __init__(self, client: InternalHttpClient) -> None:
        self._client = client

    def match(self, query: ArchitectureQuery) -> ArchitectureKnowledgeMatch:
        body = self._client.post_json(
            "/internal/architecture/match",
            _QUERY.dump_python(query, mode="json"),
            idempotent=True,
        )
        return _decode(_MATCH, body, "architecture matches")


class HttpReferenceKnowledge:
    def __init__(self, client: InternalHttpClient) -> None:
        self._client = client

    def has_published(self) -> bool:
        body = self._client.get_json("/internal/library/published")
        if not isinstance(body, dict) or not isinstance(body.get("has_published"), bool):
            raise ServiceUnavailableError("The knowledge service returned an unusable answer.")
        return bool(body["has_published"])

    def search_evidence(self, query: str) -> tuple[ReferenceEvidence, ...]:
        body = self._client.post_json("/internal/library/search", {"query": query}, idempotent=True)
        return _decode(_EVIDENCE, body, "reference evidence")

    def retrieve(self, query: str) -> tuple[ReferenceEvidence, ...]:
        body = self._client.post_json(
            "/internal/library/retrieve", {"query": query}, idempotent=True
        )
        return _decode(_EVIDENCE, body, "reference evidence")


class HttpKnowledgeEvents:
    def __init__(self, client: InternalHttpClient) -> None:
        self._client = client

    def after(self, seq: int, limit: int) -> tuple[KnowledgeEvent, ...]:
        body = self._client.get_json("/internal/events", {"after": seq, "limit": limit})
        if not isinstance(body, list):
            raise ServiceUnavailableError("The knowledge service returned unusable events.")
        events: list[KnowledgeEvent] = []
        try:
            for item in body:
                events.append(
                    KnowledgeEvent(
                        _whole(item["seq"]),
                        _text(item["kind"]),
                        _text(item["subject_id"]),
                        item["payload"],
                        datetime.fromisoformat(_text(item["created_at"])),
                    )
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServiceUnavailableError(
                "The knowledge service returned unusable events."
            ) from exc
        if any(
            later.seq <= earlier.seq for earlier, later in zip(events, events[1:], strict=False)
        ):
            raise ServiceUnavailableError("The knowledge service returned events out of order.")
        return tuple(events)


def _whole(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise TypeError("expected a positive whole number")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("expected text")
    return value


class FakeArchitectureKnowledge:
    """Maps nothing: offline, requirement work runs without catalogue impact."""

    def match(self, query: ArchitectureQuery) -> ArchitectureKnowledgeMatch:
        return ArchitectureKnowledgeMatch(
            query.release_id or "offline-catalogue",
            (),
            (),
            uncertainty="No architecture catalogue is connected.",
            evidence_classification="offline",
        )


class FakeReferenceKnowledge:
    """An empty library: nothing published, nothing found."""

    def has_published(self) -> bool:
        return False

    def search_evidence(self, query: str) -> tuple[ReferenceEvidence, ...]:
        return ()

    def retrieve(self, query: str) -> tuple[ReferenceEvidence, ...]:
        return ()


class FakeKnowledgeEvents:
    """A knowledge service that has published nothing."""

    def after(self, seq: int, limit: int) -> tuple[KnowledgeEvent, ...]:
        return ()
