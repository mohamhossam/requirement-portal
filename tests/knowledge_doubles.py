"""A stand-in for the knowledge service, for tests that cite the reference library.

The library lives in the knowledge service (ADR-0099). `PublishedLibrary` plays
its part exactly as requirement work sees it: published passages to search and
cite, and the event feed that keeps the local copy current. Publishing or
withdrawing appends the same `reference_document_changed` event the service
sends, so citation currency is decided by the real requirement code.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime

from smb_requirement_agent.application.ports.historic_corpus import (
    ContentPart,
    HistoricContentGoneError,
    HistoricContentPage,
)
from smb_requirement_agent.application.ports.knowledge_events import (
    ARCHITECTURE_RELEASE_ACTIVATED,
    HISTORIC_REQUIREMENT_CHANGED,
    REFERENCE_DOCUMENT_CHANGED,
    KnowledgeEvent,
)
from smb_requirement_agent.application.ports.reference_grounding import ReferenceEvidence
from smb_requirement_agent.domain.document.reference import (
    CurrentPublication,
    PublishedReference,
    ReferenceDocumentState,
    normalize_search,
)
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.knowledge_client import (
    OFFLINE_RELEASE_ID,
    OFFLINE_RELEASE_NAME,
    FakeArchitectureKnowledge,
    FakeKnowledgeViews,
)
from smb_requirement_agent.interfaces.api.composition.knowledge_service import KnowledgeService
from smb_requirement_agent.interfaces.api.container import Container, build_container

_WORDS = re.compile(r"\w+")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class PublishedLibrary:
    """Published passages and the event feed, as the knowledge service serves them."""

    owner_id: str = "library-owner"
    _states: dict[str, ReferenceDocumentState] = field(default_factory=dict)
    _evidence: dict[str, tuple[ReferenceEvidence, ...]] = field(default_factory=dict)
    _events: list[KnowledgeEvent] = field(default_factory=list)
    # Historic requirements, as the knowledge portal publishes them (ADR-0102).
    _historic: dict[str, dict[str, object]] = field(default_factory=dict)
    content_reads: int = 0

    def __post_init__(self) -> None:
        # The offline catalogue version is active from the start, as with the fakes.
        self.activate_release(OFFLINE_RELEASE_ID, OFFLINE_RELEASE_NAME)

    def publish(
        self, title: str, passages: Sequence[str], *, document_id: str | None = None
    ) -> tuple[PublishedReference, ...]:
        """Publish `passages` as one document's live revision; return a citation of each."""
        identifier = document_id or f"doc-{uuid.uuid4().hex[:12]}"
        previous = self._states.get(identifier)
        version_number = (
            previous.published.version_number + 1 if previous and previous.published else 1
        )
        publication = CurrentPublication(
            publication_id=f"pub-{uuid.uuid4().hex[:12]}",
            fingerprint=_sha(f"{identifier}:{version_number}:{'|'.join(passages)}"),
            version_id=f"ver-{uuid.uuid4().hex[:12]}",
            version_number=version_number,
            revision_id=f"rev-{uuid.uuid4().hex[:12]}",
            block_labels=tuple((f"block-{n}", f"Line {n}") for n in range(1, len(passages) + 1)),
            passages=tuple((f"block-{n}", text) for n, text in enumerate(passages, start=1)),
        )
        state = ReferenceDocumentState(
            identifier,
            self.owner_id,
            title,
            previous.version + 1 if previous else 1,
            publication,
        )
        citations = tuple(
            PublishedReference(
                document_id=identifier,
                title=title,
                version_id=publication.version_id,
                version_number=version_number,
                revision_id=publication.revision_id,
                publication_id=publication.publication_id,
                approval_fingerprint=publication.fingerprint,
                block_id=block,
                location=label,
                excerpt=text,
                start_offset=0,
                end_offset=len(text),
                lineage_hash=_sha(normalize_search(text)),
            )
            for (block, label), (_, text) in zip(
                publication.block_labels, publication.passages, strict=True
            )
        )
        self._changed(state)
        self._evidence[identifier] = tuple(
            ReferenceEvidence(citation, citation.excerpt, (citation.location,))
            for citation in citations
        )
        return citations

    def falls_due(self, document_id: str, on: date) -> None:
        """The library says the document falls due for review on `on` (Knowledge Center D)."""
        state = self._states[document_id]
        self._changed(replace(state, version=state.version + 1, review_due_on=on))

    def withdraw(self, document_id: str) -> None:
        """Withdraw the document's publication; its citations stop being current."""
        state = self._states[document_id]
        self._changed(replace(state, version=state.version + 1, published=None))
        self._evidence.pop(document_id, None)

    def activate_release(self, release_id: str, name: str | None = None) -> None:
        self._append(
            ARCHITECTURE_RELEASE_ACTIVATED, release_id, {"release_id": release_id, "name": name}
        )

    def publish_historic(
        self,
        title: str,
        passages: Sequence[str],
        items: Sequence[dict[str, object]] = (),
        *,
        historic_id: str | None = None,
    ) -> str:
        """Publish (or publish again) a historic requirement; return its id."""
        identifier = historic_id or str(uuid.uuid4())
        previous = self._historic.get(identifier)
        number = int(str(previous["publication"])) + 1 if previous else 1
        version = int(str(previous["version"])) + 1 if previous else 1
        entries = [
            {
                "brd_id": "brd-1",
                "filename": f"{title}.docx",
                "block_id": f"p{n}",
                "label": f"Paragraph {n}",
                "section_path": [],
                "text": text,
            }
            for n, text in enumerate(passages, start=1)
        ]
        fingerprint = _sha(f"{identifier}:{number}:{entries}:{list(items)}")
        self._historic[identifier] = {
            "publication": number,
            "version": version,
            "fingerprint": fingerprint,
            "title": title,
            "passages": entries,
            "items": list(items),
            "published": True,
        }
        self._append(
            HISTORIC_REQUIREMENT_CHANGED,
            identifier,
            {
                "historic_requirement_id": identifier,
                "version": version,
                "published": {
                    "title": title,
                    "root_ids": [item["id"] for item in items if item.get("parent_id") is None],
                    "fetched_at": "2026-10-06T09:00:00+00:00",
                    "counts": {"brds": 1, "passages": len(entries), "items": len(items)},
                    "publication": number,
                    "fingerprint": fingerprint,
                    "published_at": "2026-10-06T09:00:00+00:00",
                    "published_by": {"id": "ada", "name": "Ada Admin"},
                    "imported_at": "2026-10-06T09:00:00+00:00",
                    "imported_by": {"id": "ada", "name": "Ada Admin"},
                },
            },
        )
        return identifier

    def withdraw_historic(self, historic_id: str) -> None:
        record = self._historic[historic_id]
        record["published"] = False
        record["version"] = int(str(record["version"])) + 1
        self._append(
            HISTORIC_REQUIREMENT_CHANGED,
            historic_id,
            {
                "historic_requirement_id": historic_id,
                "version": record["version"],
                "published": None,
            },
        )

    # HistoricContentSourcePort: a publication's content, a page at a time.
    def page(
        self, historic_id: str, publication: int, part: ContentPart, offset: int, limit: int
    ) -> HistoricContentPage:
        self.content_reads += 1
        record = self._historic.get(historic_id)
        if record is None or not record["published"] or record["publication"] != publication:
            raise HistoricContentGoneError("That publication is no longer the one in use.")
        entries = list(record[part.value])  # type: ignore[call-overload]
        page = tuple(entries[offset : offset + limit])
        more = offset + limit < len(entries)
        return HistoricContentPage(
            publication, str(record["fingerprint"]), page, offset + limit if more else None
        )

    # ReferenceKnowledgePort: what requirement work searches and cites.
    def has_published(self) -> bool:
        return bool(self._evidence)

    def search_evidence(self, query: str) -> tuple[ReferenceEvidence, ...]:
        terms = set(_WORDS.findall(normalize_search(query)))
        return tuple(
            item
            for items in self._evidence.values()
            for item in items
            if terms & set(_WORDS.findall(normalize_search(item.citation.excerpt)))
        )

    def retrieve(self, query: str) -> tuple[ReferenceEvidence, ...]:
        return self.search_evidence(query)

    # KnowledgeEventSourcePort: the feed requirement work's local copy follows.
    def after(self, seq: int, limit: int) -> tuple[KnowledgeEvent, ...]:
        return tuple(event for event in self._events if event.seq > seq)[:limit]

    def _changed(self, state: ReferenceDocumentState) -> None:
        self._states[state.document_id] = state
        self._append(REFERENCE_DOCUMENT_CHANGED, state.document_id, state.to_payload())

    def _append(self, kind: str, subject_id: str, payload: object) -> None:
        self._events.append(
            KnowledgeEvent(len(self._events) + 1, kind, subject_id, payload, datetime.now(UTC))
        )


def service_for(library: PublishedLibrary) -> KnowledgeService:
    """A knowledge service whose library is `library`, with no catalogue impact."""
    return KnowledgeService(
        references=library,
        architecture=FakeArchitectureKnowledge(),
        events=library,
        views=FakeKnowledgeViews(),
        remote=False,
        historic_content=library,
    )


def container_with_library(
    settings: Settings, library: PublishedLibrary | None = None
) -> tuple[Container, PublishedLibrary]:
    """A container whose knowledge service is a `PublishedLibrary`."""
    library = library or PublishedLibrary()
    return build_container(settings, knowledge_service=service_for(library)), library


def sync(container: Container) -> None:
    """Bring requirement work's local copy up to date, as the event worker would."""
    container.knowledge_projection.drain()
    container.historic_projection.drain()


def index_historic(container: Container) -> None:
    """Read and embed every pending historic publication, as the index worker would."""
    for _ in range(10_000):
        if not container.historic_indexer.process_next():
            return


def work_item(
    item_id: int,
    kind: str,
    title: str,
    *,
    parent_id: int | None = None,
    description: str = "",
    state: str = "Closed",
) -> dict[str, object]:
    """A work item entry as the knowledge portal serves it."""
    return {
        "id": item_id,
        "type": kind,
        "title": title,
        "state": state,
        "revision": 1,
        "url": f"https://dev.azure.com/smb/_workitems/edit/{item_id}",
        "description": description,
        "acceptance_criteria": "",
        "area_path": "SMB\\Fixed",
        "iteration_path": "SMB\\2025\\Q2",
        "tags": [],
        "parent_id": parent_id,
        "child_ids": [],
    }
