"""The Requirement knowledge corpus summary for the Knowledge Center (A′).

Requirement work answers it over `/internal/knowledge/corpus/summary` with counts only:
how many Requirements, how many closed as duplicates, how many indexed, waiting or failed,
and how long the findings still in force have stood open.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import RLock

import pytest
from fastapi.testclient import TestClient
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.errors import ModelTransportError
from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirementInput
from smb_requirement_agent.application.use_cases.internal_reads import OpenFindingAges
from smb_requirement_agent.application.use_cases.requirement_indexing import (
    IndexBacklog,
    IndexBacklogReader,
    IndexRequirementKnowledge,
)
from smb_requirement_agent.domain.shared.identifiers import RequirementId
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.persistence.requirement_indexing import (
    MemoryRequirementIndexProgress,
)
from smb_requirement_agent.infrastructure.persistence.requirement_knowledge_repository import (
    InMemoryRequirementKnowledgeStore,
)
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from tests.conftest import FAKE_PROVIDER_SETTINGS
from tests.unit.test_requirement_indexing import RecordingEmbedding, corpus
from tests.unit.workflow_helpers import drain_requirement_index

TOKEN = "k" * 40
SERVICE = {"Authorization": f"Bearer {TOKEN}"}
START = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(START)


@pytest.fixture
def timed(clock: FixedClock) -> Container:
    return build_container(FAKE_PROVIDER_SETTINGS, clock=clock)


def _requirement(container: Container, title: str, description: str) -> RequirementId:
    return container.create_requirement.execute(
        CreateRequirementInput(title=title, description=description), FAKE_ACTORS[0]
    ).id


def _screen(container: Container, requirement_id: RequirementId) -> None:
    fingerprint = container.get_knowledge_review.execute(requirement_id).current_fingerprint
    drain_requirement_index(container)
    container.screen_requirement_knowledge.execute(FAKE_ACTORS[0], requirement_id, fingerprint)


def test_an_empty_portfolio_is_all_zero(timed: Container) -> None:
    summary = timed.internal_reads.corpus_summary()

    assert (summary.requirements, summary.duplicates, summary.current) == (0, 0, 0)
    assert (summary.waiting, summary.failed, summary.rebuild_required) == (0, 0, False)
    assert summary.open_findings == OpenFindingAges(0, 0, 0)
    assert summary.as_of == START


def test_new_requirements_wait_until_the_indexer_reaches_them(timed: Container) -> None:
    _requirement(timed, "Fibre ordering", "Customers order fibre online.")
    _requirement(timed, "Mobile ordering", "Customers order mobile plans online.")

    waiting = timed.internal_reads.corpus_summary()
    drain_requirement_index(timed)
    indexed = timed.internal_reads.corpus_summary()

    assert (waiting.requirements, waiting.current, waiting.waiting) == (2, 0, 2)
    assert (indexed.requirements, indexed.current, indexed.waiting) == (2, 2, 0)


def test_open_findings_are_bucketed_by_how_long_they_have_stood(
    timed: Container, clock: FixedClock
) -> None:
    _requirement(timed, "XGPON bundles", "Business customers order XGPON bundles via BCRM.")
    candidate = _requirement(
        timed, "XGPON bundles", "Business customers order XGPON bundles via BCRM."
    )
    _screen(timed, candidate)

    ages = []
    for days in (0, 6, 7, 30, 31):
        clock.set(START + timedelta(days=days))
        ages.append(timed.internal_reads.corpus_summary().open_findings)

    assert ages == [
        OpenFindingAges(1, 0, 0),
        OpenFindingAges(1, 0, 0),
        OpenFindingAges(0, 1, 0),
        OpenFindingAges(0, 1, 0),
        OpenFindingAges(0, 0, 1),
    ]


def test_a_decided_finding_leaves_the_count_and_a_duplicate_is_counted(
    timed: Container,
) -> None:
    _requirement(timed, "XGPON bundles", "Business customers order XGPON bundles via BCRM.")
    candidate = _requirement(
        timed, "XGPON bundles", "Business customers order XGPON bundles via BCRM."
    )
    _screen(timed, candidate)
    finding = timed.get_knowledge_review.execute(candidate).findings[0]

    timed.decide_knowledge_finding.execute(
        candidate, finding.id, "duplicate", finding.version, FAKE_ACTORS[0]
    )

    summary = timed.internal_reads.corpus_summary()
    assert (summary.requirements, summary.duplicates) == (2, 1)
    assert summary.open_findings == OpenFindingAges(0, 0, 0)


def test_a_finding_no_longer_in_force_is_not_counted(timed: Container) -> None:
    """The Knowledge step's rule: both Requirements at the versions the finding judged."""
    canonical = _requirement(
        timed, "XGPON bundles", "Business customers order XGPON bundles via BCRM."
    )
    candidate = _requirement(
        timed, "XGPON bundles", "Business customers order XGPON bundles via BCRM."
    )
    _screen(timed, candidate)
    stored = timed.requirement_repository.get(canonical)
    assert stored is not None

    timed.requirement_repository.save(
        stored.update(stored.title, stored.description, updated_at=START + timedelta(hours=1))
    )

    assert timed.internal_reads.corpus_summary().open_findings == OpenFindingAges(0, 0, 0)


def test_a_source_that_stopped_retrying_is_failed_until_it_changes(container: Container) -> None:
    requirement = container.create_requirement.execute(
        CreateRequirementInput(title="Coverage", description="Coverage required."), FAKE_ACTORS[0]
    )
    clock = FixedClock(START)
    embeddings = RecordingEmbedding()
    embeddings.fail = True
    progress = MemoryRequirementIndexProgress(RLock())
    indexer = IndexRequirementKnowledge(
        corpus(container),
        container.knowledge_index,
        embeddings,
        progress,
        clock,
        "A",
        container.requirement_access,
    )
    reader = IndexBacklogReader(container.knowledge_index, progress, "A")
    assert reader.backlog() == IndexBacklog(waiting=1, failed=0, rebuild_required=False)
    for _ in range(3):
        indexer.process_next()
        clock.set(clock.now() + timedelta(minutes=5))

    assert reader.backlog() == IndexBacklog(waiting=0, failed=1, rebuild_required=False)
    # Another identity's failures (another embedding model) are not this index's.
    assert IndexBacklogReader(container.knowledge_index, progress, "B").backlog().failed == 0

    # A new change is new work: it waits again, and is tried afresh.
    store = container.knowledge_index
    assert isinstance(store, InMemoryRequirementKnowledgeStore)
    store.mark_source_changed(requirement.id)
    assert reader.backlog() == IndexBacklog(waiting=1, failed=0, rebuild_required=False)


class PagedIndex:
    """Pending sources only, served page by page like the real adapters."""

    def __init__(self, count: int, *, rebuild: bool = False) -> None:
        self.sources = tuple((RequirementId(f"REQ-{i:05}"), 1) for i in range(count))
        self.rebuild = rebuild
        self.pages = 0

    def pending_sources(self, limit: int, after: str = "") -> tuple[tuple[RequirementId, int], ...]:
        if self.rebuild:
            raise ModelTransportError("index_required")
        self.pages += 1
        return tuple(item for item in self.sources if item[0].value > after)[:limit]


def _reader(index: PagedIndex) -> IndexBacklogReader:
    return IndexBacklogReader(
        index,  # type: ignore[arg-type]
        MemoryRequirementIndexProgress(RLock()),
        "A",
    )


def test_the_backlog_counts_every_page() -> None:
    index = PagedIndex(1203)

    assert _reader(index).backlog() == IndexBacklog(1203, 0, rebuild_required=False)
    assert index.pages == 4  # three full pages of 500, then the empty one that ends it


def test_a_model_change_reports_a_rebuild_not_counts() -> None:
    backlog = _reader(PagedIndex(3, rebuild=True)).backlog()

    assert backlog == IndexBacklog(0, 0, rebuild_required=True)


def test_the_route_answers_the_knowledge_service_with_counts_only(timed: Container) -> None:
    requirement = _requirement(timed, "Fibre ordering", "Customers order fibre online.")
    serving = replace(timed, settings=replace(timed.settings, knowledge_service_token=TOKEN))

    with TestClient(create_app(lambda: serving)) as client:
        refused = client.get("/internal/knowledge/corpus/summary")
        answered = client.get("/internal/knowledge/corpus/summary", headers=SERVICE)

    assert refused.status_code == 401
    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert set(body) == {
        "requirements",
        "duplicates",
        "retired",
        "current",
        "waiting",
        "failed",
        "rebuild_required",
        "open_findings",
        "as_of",
    }
    assert body["requirements"] == 1
    assert requirement.value not in answered.text
