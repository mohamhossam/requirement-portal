"""A knowledge admin's actions on the Requirement corpus (Knowledge Center B3).

Retiring takes a Requirement out of screening, knowledge search and suggestions, closes every
open finding that cites it as "source retired", and tells its owner; it stays readable and keeps
its version. Reinstating returns it and makes its earlier screen stale. Bulk retry and reindex
only reset failure counts or mark sources changed, for the index worker to do.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import RLock

import pytest
from fastapi.testclient import TestClient
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.jobs.domain.entities import NotificationKind
from smb_requirement_agent.knowledge.application.ports.knowledge_portfolio import IndexState
from smb_requirement_agent.knowledge.application.use_cases.corpus_actions import (
    BulkReindexRequirements,
)
from smb_requirement_agent.knowledge.application.use_cases.requirement_indexing import (
    IndexBacklogReader,
)
from smb_requirement_agent.knowledge.domain.entities import (
    KnowledgeDecisionKind,
    KnowledgeFindingStatus,
)
from smb_requirement_agent.knowledge.domain.membership import CorpusActionKind
from smb_requirement_agent.knowledge.domain.screening_errors import (
    CorpusMembershipConflictError,
    KnowledgeFindingConflictError,
    RequirementRetiredError,
)
from smb_requirement_agent.knowledge.infrastructure.corpus_membership import (
    InMemoryCorpusActions,
)
from smb_requirement_agent.knowledge.infrastructure.llm.fake_requirement_knowledge import (
    FakeKnowledgeEmbedding,
)
from smb_requirement_agent.knowledge.infrastructure.requirement_indexing import (
    MemoryRequirementIndexProgress,
)
from smb_requirement_agent.knowledge.infrastructure.requirement_knowledge_repository import (
    InMemoryRequirementKnowledgeStore,
)
from smb_requirement_agent.references.domain.errors import InvalidKnowledgeError
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirementInput,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.conftest import FAKE_PROVIDER_SETTINGS
from tests.unit.workflow_helpers import drain_requirement_index

TOKEN = "k" * 40
SERVICE = {"Authorization": f"Bearer {TOKEN}"}
START = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)
AMINA, RAVI, OMAR = FAKE_ACTORS
XGPON = "Business customers order XGPON bundles via BCRM."
REASON = "Cancelled: the XGPON launch moved to the 2027 plan."


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(START)


@pytest.fixture
def timed(clock: FixedClock) -> Container:
    return build_container(FAKE_PROVIDER_SETTINGS, clock=clock)


def _requirement(
    container: Container, title: str, description: str, owner: ActorProfile = AMINA
) -> RequirementId:
    return container.create_requirement.execute(
        CreateRequirementInput(title=title, description=description), owner
    ).id


def _screen(
    container: Container, requirement_id: RequirementId, owner: ActorProfile = AMINA
) -> None:
    fingerprint = container.get_knowledge_review.execute(requirement_id).current_fingerprint
    drain_requirement_index(container)
    container.screen_requirement_knowledge.execute(owner, requirement_id, fingerprint)


def _duplicates(container: Container) -> tuple[RequirementId, RequirementId]:
    """Ravi's Requirement and Amina's, screened as possible duplicates."""
    canonical = _requirement(container, "XGPON bundles", XGPON, RAVI)
    candidate = _requirement(container, "XGPON bundles for offices", XGPON, AMINA)
    _screen(container, candidate)
    assert container.get_knowledge_review.execute(candidate).findings
    return canonical, candidate


def _retire(container: Container, requirement_id: RequirementId) -> object:
    return container.retire_from_corpus.execute(
        requirement_id.value, OMAR.id.value, OMAR.display_name, REASON
    )


def _reinstate(container: Container, requirement_id: RequirementId) -> object:
    return container.reinstate_to_corpus.execute(
        requirement_id.value, OMAR.id.value, OMAR.display_name, "The launch is back on."
    )


def _indexed(container: Container, requirement_id: RequirementId) -> bool:
    (query,) = FakeKnowledgeEmbedding().embed(("XGPON",))
    return any(
        match.chunk.requirement_id == requirement_id
        for match in container.knowledge_index.search("XGPON", query, None, 1000)
    )


def _notes(container: Container, owner: ActorProfile, kind: NotificationKind) -> list[str]:
    return [
        item.message
        for item in container.notification_repository.list_for_actor(owner.id)
        if item.kind is kind
    ]


def _actions(container: Container) -> InMemoryCorpusActions:
    actions = container.retire_from_corpus._actions  # noqa: SLF001 - the memory audit trail
    assert isinstance(actions, InMemoryCorpusActions)
    return actions


def test_retiring_closes_the_findings_that_cite_it_and_tells_the_owner(timed: Container) -> None:
    canonical, candidate = _duplicates(timed)
    before = timed.requirement_repository.get(canonical)

    result = _retire(timed, canonical)

    finding = timed.get_knowledge_review.execute(candidate).findings[0]
    assert finding.status is KnowledgeFindingStatus.SOURCE_RETIRED
    decision = finding.decisions[-1]
    assert decision.kind is KnowledgeDecisionKind.SOURCE_RETIRED
    assert (decision.actor.id, decision.actor.display_name) == (OMAR.id, OMAR.display_name)
    assert decision.rationale == REASON
    assert result.closed_findings == 1  # type: ignore[attr-defined]
    assert result.notified == RAVI.display_name  # type: ignore[attr-defined]
    (note,) = _notes(timed, RAVI, NotificationKind.KNOWLEDGE_CORPUS_RETIRED)
    assert note == f"Omar Observer retired ‘XGPON bundles’ from the knowledge corpus: {REASON}"
    # The Requirement itself is untouched: readable, at the same version.
    assert timed.requirement_repository.get(canonical) == before
    (action,) = _actions(timed).actions
    assert (action.kind, action.requirement_ids, action.reason) == (
        CorpusActionKind.RETIRE,
        (canonical,),
        REASON,
    )


def test_a_retired_requirement_is_out_of_screening_search_and_suggestions(
    timed: Container,
) -> None:
    canonical, candidate = _duplicates(timed)
    drain_requirement_index(timed)
    assert _indexed(timed, canonical)

    _retire(timed, canonical)
    drain_requirement_index(timed)

    assert not _indexed(timed, canonical)
    _screen(timed, candidate)
    assert not [
        item
        for item in timed.get_knowledge_review.execute(candidate).findings
        if item.status is KnowledgeFindingStatus.OPEN
    ]
    retired = timed.get_knowledge_review.execute(canonical)
    assert retired.retirement is not None and retired.retirement.reason == REASON
    assert retired.current and retired.ready
    with pytest.raises(RequirementRetiredError):
        timed.ensure_knowledge_screen.execute(canonical, RAVI)
    found = timed.unified_knowledge_search.execute("XGPON bundles")
    assert all(item.source_id != canonical.value for item in found)


def test_reinstating_returns_it_and_its_next_screen_raises_findings_afresh(
    timed: Container, clock: FixedClock
) -> None:
    canonical, candidate = _duplicates(timed)
    closed = timed.get_knowledge_review.execute(candidate).findings[0].id
    _retire(timed, canonical)
    drain_requirement_index(timed)
    clock.set(START + timedelta(days=1))

    _reinstate(timed, canonical)

    (note,) = _notes(timed, RAVI, NotificationKind.KNOWLEDGE_CORPUS_REINSTATED)
    assert "returned ‘XGPON bundles’ to the knowledge corpus" in note
    review = timed.get_knowledge_review.execute(canonical)
    assert review.retirement is None
    drain_requirement_index(timed)
    assert _indexed(timed, canonical)
    _screen(timed, candidate)
    (fresh,) = timed.get_knowledge_review.execute(candidate).findings
    assert fresh.id != closed
    assert fresh.status is KnowledgeFindingStatus.OPEN
    earlier = timed.knowledge_repository.get_finding(closed)
    assert earlier is not None and earlier.status is KnowledgeFindingStatus.SOURCE_RETIRED
    assert [item.kind for item in _actions(timed).actions] == [
        CorpusActionKind.RETIRE,
        CorpusActionKind.REINSTATE,
    ]


def test_a_reinstated_requirements_earlier_screen_is_stale(timed: Container) -> None:
    canonical, _ = _duplicates(timed)
    _screen(timed, canonical, RAVI)
    assert timed.get_knowledge_review.execute(canonical).current

    _retire(timed, canonical)
    _reinstate(timed, canonical)

    assert not timed.get_knowledge_review.execute(canonical).current


def test_a_finding_closed_as_source_retired_cannot_be_reopened(timed: Container) -> None:
    _, candidate = _duplicates(timed)
    finding = timed.get_knowledge_review.execute(candidate).findings[0]
    closed = finding.close_source_retired(OMAR.snapshot(), REASON, START)

    with pytest.raises(KnowledgeFindingConflictError):
        closed.close_source_retired(OMAR.snapshot(), REASON, START)
    with pytest.raises(KnowledgeFindingConflictError):
        closed.propose_resolution(AMINA, "Both stand.", START, closed.version)


def test_corpus_actions_refuse_what_does_not_fit(timed: Container) -> None:
    canonical, candidate = _duplicates(timed)

    with pytest.raises(InvalidKnowledgeError):
        timed.retire_from_corpus.execute(canonical.value, OMAR.id.value, OMAR.display_name, " ")
    with pytest.raises(CorpusMembershipConflictError, match="not retired"):
        _reinstate(timed, canonical)
    _retire(timed, canonical)
    with pytest.raises(CorpusMembershipConflictError, match="already retired it on 7 Oct 2026"):
        _retire(timed, canonical)
    finding = timed.get_knowledge_review.execute(candidate).findings[0]
    assert finding.status is KnowledgeFindingStatus.SOURCE_RETIRED

    other = _requirement(timed, "Archive", "Old copper orders.", RAVI)
    duplicate = _requirement(timed, "Archive again", "Old copper orders.", AMINA)
    _screen(timed, duplicate)
    pair = timed.get_knowledge_review.execute(duplicate).findings[0]
    assert pair.related_requirement_id == other
    timed.decide_knowledge_finding.execute(duplicate, pair.id, "duplicate", pair.version, AMINA)
    with pytest.raises(CorpusMembershipConflictError, match="closed as a duplicate"):
        _retire(timed, duplicate)


def test_a_retired_requirement_cannot_be_chosen_as_canonical(timed: Container) -> None:
    canonical, candidate = _duplicates(timed)
    finding = timed.get_knowledge_review.execute(candidate).findings[0]
    timed.retire_from_corpus.execute(canonical.value, OMAR.id.value, OMAR.display_name, REASON)
    # Its finding closed; a fresh pair with a retired side is refused before the domain rule.
    with pytest.raises(KnowledgeFindingConflictError):
        timed.decide_knowledge_finding.execute(
            candidate, finding.id, "duplicate", finding.version, AMINA
        )


def test_reindex_marks_only_the_chosen_requirements(timed: Container) -> None:
    first = _requirement(timed, "Fibre ordering", "Customers order fibre online.")
    second = _requirement(timed, "Mobile ordering", "Customers order mobile plans online.")
    drain_requirement_index(timed)
    store = timed.knowledge_index
    assert isinstance(store, InMemoryRequirementKnowledgeStore)
    before = dict(store.source_versions())

    result = timed.bulk_reindex.reindex(
        (first.value, first.value, "unknown"), OMAR.id.value, OMAR.display_name, None
    )

    after = dict(store.source_versions())
    assert result.requirements == 1
    assert after[first] == before[first] + 1
    assert after[second] == before[second]
    with pytest.raises(CorpusMembershipConflictError):
        timed.bulk_reindex.reindex((), OMAR.id.value, OMAR.display_name, None)


def test_retry_resets_only_sources_that_stopped_retrying(timed: Container) -> None:
    stuck = _requirement(timed, "Fibre ordering", "Customers order fibre online.")
    waiting = _requirement(timed, "Mobile ordering", "Customers order mobile plans online.")
    progress = MemoryRequirementIndexProgress(RLock())
    changes = dict(timed.knowledge_index.pending_sources(10))
    claimed = progress.claim(
        "A", stuck.value, changes[stuck], "t", START, START + timedelta(hours=1)
    )
    assert claimed is not None
    progress.save("A", stuck.value, "t", replace(claimed, failures=3), START)
    actions = InMemoryCorpusActions(RLock())
    bulk = BulkReindexRequirements(
        IndexBacklogReader(timed.knowledge_index, progress, "A"),
        timed.bulk_reindex._source_changes,  # noqa: SLF001
        actions,
        timed.transaction_manager,
        FixedClock(START + timedelta(hours=2)),
    )

    result = bulk.retry_failed(OMAR.id.value, OMAR.display_name, "Provider is back.")

    assert result.requirements == 1
    assert progress.get("A", stuck.value).failures == 0
    assert progress.get("A", waiting.value).failures == 0
    (action,) = actions.actions
    assert (action.kind, action.requirement_ids) == (CorpusActionKind.RETRY, (stuck,))


def test_retired_requirements_are_counted_and_filtered(timed: Container) -> None:
    canonical, _ = _duplicates(timed)
    _retire(timed, canonical)

    summary = timed.internal_reads.corpus_summary()
    page = timed.knowledge_portfolio.corpus(
        index_state=None,
        owner_id=None,
        text="",
        open_findings_only=False,
        not_screened_for_days=None,
        offset=0,
        limit=50,
        retired_only=True,
    )

    assert summary.retired == 1
    # Retired has left the corpus: it is none of current, waiting or failed.
    drain_requirement_index(timed)
    settled = timed.internal_reads.corpus_summary()
    assert (settled.requirements, settled.current, settled.waiting) == (2, 1, 0)
    current = timed.knowledge_portfolio.corpus(
        index_state=IndexState.CURRENT,
        owner_id=None,
        text="",
        open_findings_only=False,
        not_screened_for_days=None,
        offset=0,
        limit=50,
    )
    assert canonical.value not in {item.requirement_id for item in current.items}
    (row,) = page.items
    assert row.requirement_id == canonical.value
    assert row.retired is not None
    assert (row.retired.by, row.retired.reason, row.retired.at) == (
        OMAR.display_name,
        REASON,
        START,
    )


def test_the_routes_need_the_token_and_pass_refusals_through(timed: Container) -> None:
    canonical, _ = _duplicates(timed)
    serving = replace(timed, settings=replace(timed.settings, knowledge_service_token=TOKEN))
    body = {"actor_id": OMAR.id.value, "actor_name": OMAR.display_name, "reason": REASON}
    retire = f"/internal/knowledge/requirements/{canonical.value}/retirement"

    with TestClient(create_app(lambda: serving)) as client:
        refused = client.post(retire, json=body)
        retired = client.post(retire, json=body, headers=SERVICE)
        again = client.post(retire, json=body, headers=SERVICE)
        blank = client.post(retire, json={**body, "reason": ""}, headers=SERVICE)
        missing = client.post(
            "/internal/knowledge/requirements/missing/retirement", json=body, headers=SERVICE
        )
        reinstated = client.post(
            f"/internal/knowledge/requirements/{canonical.value}/reinstatement",
            json=body,
            headers=SERVICE,
        )
        retried = client.post(
            "/internal/knowledge/reindex",
            json={"actor_id": "a", "actor_name": "A", "scope": "failed"},
            headers=SERVICE,
        )
        reindexed = client.post(
            "/internal/knowledge/reindex",
            json={
                "actor_id": "a",
                "actor_name": "A",
                "scope": "requirements",
                "requirement_ids": [canonical.value],
            },
            headers=SERVICE,
        )
        unknown_scope = client.post(
            "/internal/knowledge/reindex",
            json={"actor_id": "a", "actor_name": "A", "scope": "everything"},
            headers=SERVICE,
        )

    assert refused.status_code == 401
    assert retired.status_code == 200, retired.text
    assert retired.json()["state"] == "retired"
    assert retired.json()["closed_findings"] == 1
    assert again.status_code == 409
    assert "already retired" in again.json()["message"]
    assert blank.status_code == 422
    assert missing.status_code == 404
    assert reinstated.status_code == 200 and reinstated.json()["state"] == "active"
    assert retried.status_code == 200 and retried.json() == {"requirements": 0}
    assert reindexed.status_code == 200 and reindexed.json() == {"requirements": 1}
    assert unknown_scope.status_code == 422


def test_no_passage_of_a_retired_requirement_stays_in_the_index(timed: Container) -> None:
    """Every passage kind leaves: typed text, analysis and attachments (B1) alike."""
    canonical, _ = _duplicates(timed)
    drain_requirement_index(timed)

    _retire(timed, canonical)
    drain_requirement_index(timed)

    (query,) = FakeKnowledgeEmbedding().embed(("",))
    assert not [
        match
        for match in timed.knowledge_index.search("", query, None, 10_000)
        if match.chunk.requirement_id == canonical
    ]
