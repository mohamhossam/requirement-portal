"""Historic requirements: the local copy, its own cursor, and the historic corpus (ADR-0102)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.references.application.ports.historic_corpus import ContentPart
from smb_requirement_agent.references.application.use_cases.historic_corpus import (
    CHUNKS_PER_RECORD,
    SPANS_PER_ENTRY,
    historic_chunks,
)
from smb_requirement_agent.references.domain.errors import InvalidKnowledgeError
from smb_requirement_agent.references.domain.historic import (
    HistoricSourceKind,
    HistoricWorkItem,
    ancestors,
    safe_url,
)
from smb_requirement_agent.references.infrastructure.historic_corpus import any_of
from smb_requirement_agent.references.infrastructure.knowledge_payloads import (
    historic_requirement_state_from_payload,
    historic_requirement_state_to_payload,
)
from tests.knowledge_doubles import (
    PublishedLibrary,
    container_with_library,
    index_historic,
    sync,
    work_item,
)

EXAMPLE = (
    Path(__file__).resolve().parents[3] / "contracts" / "historic-requirement-changed.example.json"
)

BACKLOG = (
    work_item(48213, "epic", "XGPON fibre bundles for small offices"),
    work_item(48214, "feature", "Order an XGPON bundle in BCRM", parent_id=48213),
    work_item(
        48216,
        "user_story",
        "As a sales agent, I choose an XGPON bundle for an SMB account",
        parent_id=48214,
        description="Only covered addresses offer the bundle.",
    ),
)


@pytest.fixture
def served() -> tuple[Container, PublishedLibrary]:
    return container_with_library(Settings(llm_provider=LLMProvider.FAKE))


def _search(container: Container, text: str) -> list[str]:
    identity = container.historic_indexer.identity
    vector = container.historic_indexer._embeddings.embed((text,))[0]  # noqa: SLF001
    matches = container.historic_corpus.search(text, vector, identity, 20)
    return [match.chunk.historic_id for match in matches]


# --- The event, as the knowledge portal sends it --------------------------------------------


def test_the_knowledge_portal_s_pinned_event_is_read() -> None:
    state = historic_requirement_state_from_payload(json.loads(EXAMPLE.read_text()))
    assert state.published is not None
    assert state.published.number == 1 and state.published.title == "XGPON bundles"
    assert state.published.root_ids == (48213,)
    withdrawn = historic_requirement_state_from_payload(
        {"historic_requirement_id": state.historic_requirement_id, "version": 9, "published": None}
    )
    assert withdrawn.published is None
    # A copy round-trips through what requirement work stores.
    assert (
        historic_requirement_state_from_payload(historic_requirement_state_to_payload(state))
        == state
    )


def test_a_malformed_event_is_refused() -> None:
    for payload in (
        None,
        {"historic_requirement_id": "h", "version": 0, "published": None},
        {"historic_requirement_id": "h", "version": 1, "published": {"publication": 1}},
    ):
        with pytest.raises(InvalidKnowledgeError):
            historic_requirement_state_from_payload(payload)


def test_only_web_addresses_become_links_and_lineage_is_epic_first() -> None:
    assert safe_url(" https://dev.azure.com/x ") == "https://dev.azure.com/x"
    assert safe_url("javascript:alert(1)") is None
    items = {entry.id: entry for entry in map(HistoricWorkItem.from_entry, BACKLOG)}
    assert [item.id for item in ancestors(items, 48216)] == [48213, 48214, 48216]
    # A cycle in what was read never loops.
    looped = {
        1: HistoricWorkItem.from_entry(work_item(1, "epic", "A", parent_id=2)),
        2: HistoricWorkItem.from_entry(work_item(2, "feature", "B", parent_id=1)),
    }
    assert [item.id for item in ancestors(looped, 1)] == [2, 1]


def test_chunks_keep_where_they_came_from_and_stay_bounded() -> None:
    passage = {
        "brd_id": "b1",
        "filename": "BRD-2025-014.docx",
        "block_id": "p2",
        "label": "Paragraph 2",
        "section_path": ["Scope"],
        "text": "Business customers order XGPON fibre bundles.",
    }
    chunks = historic_chunks("h1", {ContentPart.PASSAGES: (passage,), ContentPart.ITEMS: BACKLOG})
    brd = [c for c in chunks if c.source_kind is HistoricSourceKind.HISTORIC_BRD]
    assert brd[0].field == "brd:b1:p2" and brd[0].evidence["label"] == "Paragraph 2"
    story = next(c for c in chunks if c.field == "item:48216")
    assert story.text.startswith("User Story #48216 As a sales agent")
    lineage = cast(list[dict[str, object]], story.evidence["lineage"])
    assert [link["id"] for link in lineage] == [48213, 48214, 48216]
    # Ids are stable, so the same content keeps the same chunks.
    again = historic_chunks("h1", {ContentPart.PASSAGES: (passage,), ContentPart.ITEMS: BACKLOG})
    assert [c.chunk_id for c in again] == [c.chunk_id for c in chunks]
    # A very long description is cut to a bounded number of spans.
    long_story = work_item(9, "user_story", "Long", description="word " * 5000)
    assert len(historic_chunks("h2", {ContentPart.ITEMS: (long_story,)})) == SPANS_PER_ENTRY
    assert CHUNKS_PER_RECORD == 20_000


# --- The projection ------------------------------------------------------------------------


def test_publications_made_before_requirement_work_read_them_are_projected_from_zero(
    served: tuple[Container, PublishedLibrary],
) -> None:
    container, library = served
    sync(container)
    reference_cursor = container.knowledge_projection._states.cursor()  # noqa: SLF001
    historic_id = library.publish_historic("XGPON bundles", ["XGPON fibre for offices."], BACKLOG)
    library.publish("A policy", ["Unrelated reference text."])
    sync(container)
    state = container.historic_corpus.get(historic_id)
    assert state is not None and state.published is not None and state.published.number == 1
    # Each consumer keeps its own cursor; both have read every event.
    assert container.historic_corpus.cursor() == len(library._events)  # noqa: SLF001
    assert container.knowledge_projection._states.cursor() > reference_cursor  # noqa: SLF001
    # An older event never replaces a newer one.
    assert not container.historic_corpus.apply(1, state)


def test_a_publication_becomes_searchable_only_once_read_and_embedded_in_full(
    served: tuple[Container, PublishedLibrary],
) -> None:
    container, library = served
    historic_id = library.publish_historic(
        "XGPON bundles", [f"XGPON passage {n} about fibre bundles." for n in range(450)], BACKLOG
    )
    sync(container)
    identity = container.historic_indexer.identity
    assert container.historic_corpus.version() == 0
    # One step reads one page; nothing is searchable until every chunk has its vector.
    assert container.historic_indexer.process_next()
    assert not container.historic_corpus.has_content(identity)
    index_historic(container)
    assert library.content_reads == 4  # 450 passages in three pages, then the items.
    assert container.historic_corpus.has_content(identity)
    assert container.historic_corpus.version() == 1
    assert historic_id in _search(container, "XGPON fibre bundles")


def test_a_withdrawal_stops_search_at_once_and_a_republication_takes_over(
    served: tuple[Container, PublishedLibrary],
) -> None:
    container, library = served
    kept = library.publish_historic("Gulf roaming", ["Roaming packs for the Gulf."])
    gone = library.publish_historic("XGPON bundles", ["XGPON fibre for offices."], BACKLOG)
    sync(container)
    index_historic(container)
    assert gone in _search(container, "XGPON fibre")
    library.withdraw_historic(gone)
    sync(container)  # No indexing needed: the projection removes it.
    assert gone not in _search(container, "XGPON fibre")
    assert kept in _search(container, "Roaming packs")
    version = container.historic_corpus.version()
    library.publish_historic(
        "Gulf roaming", ["Roaming packs for the Gulf and Levant."], historic_id=kept
    )
    sync(container)
    # Until the new publication is read in full, the previous one is what is searched.
    assert kept in _search(container, "Roaming packs")
    index_historic(container)
    assert container.historic_corpus.version() == version + 1
    standing = container.historic_corpus.standing((kept, gone))
    assert standing[kept].publication == 2 and not standing[gone].published


def test_a_superseded_publication_is_dropped_and_the_newer_one_read(
    served: tuple[Container, PublishedLibrary],
) -> None:
    container, library = served
    historic_id = library.publish_historic("XGPON bundles", ["First text."])
    sync(container)
    # The knowledge portal moves on before requirement work has read the first publication.
    library.publish_historic("XGPON bundles", ["Second text about fibre."], historic_id=historic_id)
    container.historic_indexer.process_next()  # Told the first is gone; waits for the event.
    sync(container)
    container.historic_corpus.defer(historic_id, container.historic_indexer._clock.now())  # noqa: SLF001
    index_historic(container)
    assert historic_id in _search(container, "Second text about fibre")


def test_the_hourly_embedding_budget_holds_a_large_record_back(
    served: tuple[Container, PublishedLibrary],
) -> None:
    container, library = served
    container.historic_indexer._embed_per_hour = 16  # noqa: SLF001
    library.publish_historic("Big BRD", [f"Passage number {n} of a big BRD." for n in range(40)])
    sync(container)
    index_historic(container)
    # Sixteen embedded this hour; the rest waits for the next, so nothing is searchable yet.
    assert not container.historic_corpus.has_content(container.historic_indexer.identity)


def test_lexical_search_asks_for_any_of_a_bounded_set_of_words() -> None:
    assert any_of("O'Brien's bundle, bundle!") == "'o' | 'brien' | 's' | 'bundle'"
    assert any_of("") == ""
    assert any_of(" ".join(f"w{n}" for n in range(100))).count("|") == 63
