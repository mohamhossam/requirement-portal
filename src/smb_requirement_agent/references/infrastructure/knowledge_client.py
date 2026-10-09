"""Requirement work's adapters onto the knowledge service's internal API (ADR-0099).

Each decodes the response into this application's own contract values and
fails as `ServiceUnavailableError` when it cannot: a malformed answer never
reaches the domain, and never leaks as a `KeyError` or `ValidationError`.
The fakes are deterministic stand-ins for running without the knowledge service.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from pydantic import TypeAdapter
from smb_kernel.errors import ServiceResponseError, ServiceUnavailableError
from smb_kernel.http.client import InternalHttpClient

from smb_requirement_agent.references.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureQuery,
)
from smb_requirement_agent.references.application.ports.historic_corpus import (
    ContentPart,
    HistoricContentGoneError,
    HistoricContentPage,
)
from smb_requirement_agent.references.application.ports.knowledge_events import KnowledgeEvent
from smb_requirement_agent.references.application.ports.knowledge_views import (
    ArchitectureEvidence,
    CitedPassage,
    PassageCitation,
)
from smb_requirement_agent.references.application.ports.reference_grounding import ReferenceEvidence
from smb_requirement_agent.references.domain.architecture.catalogue import SystemReference

_QUERY = TypeAdapter(ArchitectureQuery)
_MATCH = TypeAdapter(ArchitectureKnowledgeMatch)
_EVIDENCE = TypeAdapter(tuple[ReferenceEvidence, ...])
_PASSAGE = TypeAdapter(CitedPassage)
_ARCHITECTURE_EVIDENCE = TypeAdapter(ArchitectureEvidence)
# What the knowledge service answers when a view is absent: not found, or no longer live.
_ABSENT = frozenset({404, 409})


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

    def is_connected(self) -> bool:
        return True

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


class HttpKnowledgeViews:
    """The read-only viewers' reads; an absent passage or evidence is `None`, not an error."""

    def __init__(self, client: InternalHttpClient) -> None:
        self._client = client

    def passage(self, citation: PassageCitation) -> CitedPassage | None:
        body = self._absent_or(
            "/internal/library/passages",
            {
                "document_id": citation.document_id,
                "publication_id": citation.publication_id,
                "version_id": citation.version_id,
                "revision_id": citation.revision_id,
                "block_id": citation.block_id,
            },
        )
        return None if body is None else _decode(_PASSAGE, body, "a cited passage")

    def evidence(self, release_id: str, chunk_id: str) -> ArchitectureEvidence | None:
        body = self._absent_or(
            f"/internal/architecture/releases/{quote(release_id, safe='')}"
            f"/evidence/{quote(chunk_id, safe='')}",
            None,
        )
        return None if body is None else _decode(_ARCHITECTURE_EVIDENCE, body, "evidence")

    def _absent_or(self, path: str, params: dict[str, str] | None) -> Any:
        try:
            return self._client.get_json(path, params)
        except ServiceResponseError as refused:
            if refused.status_code in _ABSENT:
                return None
            raise


class HttpHistoricContent:
    """A published historic requirement's content, a page at a time (ADR-0102, amendment 1).

    An older publication (409) or a withdrawn record (404) is `HistoricContentGoneError`:
    a newer event says what to read instead.
    """

    def __init__(self, client: InternalHttpClient) -> None:
        self._client = client

    def page(
        self, historic_id: str, publication: int, part: ContentPart, offset: int, limit: int
    ) -> HistoricContentPage:
        try:
            body = self._client.get_json(
                f"/internal/historic-requirements/{quote(historic_id, safe='')}/{part.value}",
                {"publication": publication, "offset": offset, "limit": limit},
            )
        except ServiceResponseError as refused:
            if refused.status_code in _ABSENT:
                raise HistoricContentGoneError(
                    "That publication is no longer the one in use."
                ) from refused
            raise
        try:
            if not isinstance(body, dict) or not isinstance(body["entries"], list):
                raise TypeError("expected a page")
            following = body["next_offset"]
            return HistoricContentPage(
                _whole(body["publication"]),
                _text(body["fingerprint"]),
                tuple(body["entries"]),
                None if following is None else _whole(following),
            )
        except (KeyError, TypeError) as exc:
            raise ServiceUnavailableError(
                "The knowledge service returned an unusable historic page."
            ) from exc


class HttpChangeRequestInbox:
    """The knowledge service's inbox of change requests (ADR-0101 Amendment 2)."""

    def __init__(self, client: InternalHttpClient) -> None:
        self._client = client

    def deliver(self, export: dict[str, Any]) -> str:
        # Idempotent by approval: the same export delivered twice is one change request.
        body = self._client.post_json("/internal/change-requests", export, idempotent=True)
        if not isinstance(body, dict):
            raise ServiceUnavailableError("The knowledge service returned an unusable receipt.")
        try:
            return _text(body["change_request_id"])
        except (KeyError, TypeError) as exc:
            raise ServiceUnavailableError(
                "The knowledge service returned an unusable receipt."
            ) from exc


def _whole(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise TypeError("expected a positive whole number")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("expected text")
    return value


# The one catalogue version an offline knowledge service announces.
OFFLINE_RELEASE_ID = "offline-catalogue"
OFFLINE_RELEASE_NAME = "Offline catalogue"


class FakeArchitectureKnowledge:
    """An empty catalogue: offline, only the systems a Requirement declares are mapped.

    Each declared system is reported as not catalogued, the way the knowledge
    service reports a declared system it does not know. Nothing is matched from
    the text, so cross-system review still works offline without inventing a
    catalogue.
    """

    def match(self, query: ArchitectureQuery) -> ArchitectureKnowledgeMatch:
        declared: dict[str, SystemReference] = {}
        for raw in query.declared_systems:
            key = _normalise(raw)
            if key and key not in declared:
                identity = hashlib.sha256(key.encode()).hexdigest()[:12]
                declared[key] = SystemReference(f"declared-{identity}", raw.strip(), False)
        return ArchitectureKnowledgeMatch(
            query.release_id or OFFLINE_RELEASE_ID,
            tuple(declared.values()),
            (),
            uncertainty="No architecture catalogue is connected.",
            # Nothing was inferred: offline there is no model behind the empty answer.
            evidence_classification="legacy_deterministic",
        )


class FakeReferenceKnowledge:
    """An empty library: nothing published, nothing found."""

    def is_connected(self) -> bool:
        return False

    def has_published(self) -> bool:
        return False

    def search_evidence(self, query: str) -> tuple[ReferenceEvidence, ...]:
        return ()

    def retrieve(self, query: str) -> tuple[ReferenceEvidence, ...]:
        return ()


class FakeKnowledgeEvents:
    """A knowledge service with no library that has activated one empty catalogue version.

    The activation lets requirement work pin and review mappings offline, against
    the version `FakeArchitectureKnowledge` answers for.
    """

    _ACTIVATION = KnowledgeEvent(
        1,
        "architecture_release_activated",
        OFFLINE_RELEASE_ID,
        {"release_id": OFFLINE_RELEASE_ID, "name": OFFLINE_RELEASE_NAME},
        datetime(2026, 10, 2, tzinfo=UTC),
    )

    def after(self, seq: int, limit: int) -> tuple[KnowledgeEvent, ...]:
        return (self._ACTIVATION,) if seq < 1 and limit > 0 else ()


class FakeHistoricContent:
    """Offline there are no historic requirements, so there is nothing to read."""

    def page(
        self, historic_id: str, publication: int, part: ContentPart, offset: int, limit: int
    ) -> HistoricContentPage:
        raise HistoricContentGoneError("No historic requirement is published offline.")


class FakeKnowledgeViews:
    """Nothing to show: offline, no passage or evidence is published."""

    def passage(self, citation: PassageCitation) -> CitedPassage | None:
        return None

    def evidence(self, release_id: str, chunk_id: str) -> ArchitectureEvidence | None:
        return None


def _normalise(value: str) -> str:
    """The same spelling of a system name, whatever its case and punctuation."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())
