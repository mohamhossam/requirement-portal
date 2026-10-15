"""The in-memory reverse lineage index: membership, filters, counts and decisions.

The PostgreSQL twin is exercised by the integration suite; this covers the
in-memory adapter the API tests run on, whose `page` filters were previously
reached only incidentally.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.identity.application.ports.access_repository import (
    AccessRepositoryPort,
)
from smb_requirement_agent.knowledge.application.ports.source_dependencies import (
    SourceDependency,
)
from smb_requirement_agent.knowledge.domain.lineage import ImpactDecision, ImpactDecisionKind
from smb_requirement_agent.knowledge.infrastructure.source_dependencies import (
    InMemorySourceDependencies,
)
from smb_requirement_agent.shared_kernel.actors import ActorId, ActorSnapshot
from smb_requirement_agent.shared_kernel.citation import PublishedReference
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.lineage import SourceLineage

MEMBER = ActorId("member-1")


class _Membership:
    """Only `get_requirement(...).includes(actor)` is read by the adapter."""

    def __init__(self, accessible: set[str]) -> None:
        self._accessible = accessible

    def get_requirement(self, requirement_id: RequirementId) -> object | None:
        if requirement_id.value not in self._accessible:
            return None

        class _Access:
            @staticmethod
            def includes(actor_id: ActorId) -> bool:
                return actor_id == MEMBER

        return _Access()


def _store(accessible: set[str]) -> InMemorySourceDependencies:
    return InMemorySourceDependencies(cast(AccessRepositoryPort, _Membership(accessible)))


def _dependency(
    dependency_id: str,
    requirement_id: str = "req-1",
    *,
    document_id: str = "doc-1",
    target_kind: str = "constraint",
    statement: str = "Only XGPON areas qualify",
    title: str = "Fibre bundles",
    active: bool = True,
    current: bool = True,
) -> SourceDependency:
    citation = PublishedReference(
        document_id=document_id,
        title="Coverage policy",
        version_id="version-1",
        version_number=1,
        revision_id="revision-1",
        publication_id="publication-1",
        approval_fingerprint="a" * 64,
        block_id="block-1",
        location="Section 2",
        excerpt="XGPON coverage",
        start_offset=0,
        end_offset=14,
        lineage_hash="b" * 64,
    )
    return SourceDependency(
        id=dependency_id,
        requirement_id=requirement_id,
        requirement_title=title,
        target_kind=target_kind,
        target_id=f"{target_kind}-1",
        statement=statement,
        content_fingerprint="content",
        lineage=SourceLineage(citation=citation),
        active=active,
        current=current,
    )


def test_page_shows_only_requirements_the_actor_is_a_member_of() -> None:
    store = _store(accessible={"req-1"})
    store.replace_current("req-1", (_dependency("dep-1", "req-1"),))
    store.replace_current("req-2", (_dependency("dep-2", "req-2"),))

    visible = store.page(MEMBER)
    assert [row.id for row in visible] == ["dep-1"]
    assert store.page(ActorId("stranger")) == ()


def test_page_filters_compose_and_match_case_insensitively() -> None:
    store = _store(accessible={"req-1", "req-2"})
    store.replace_current(
        "req-1",
        (
            _dependency("dep-1", "req-1", document_id="doc-1", target_kind="constraint"),
            _dependency(
                "dep-2",
                "req-1",
                document_id="doc-2",
                target_kind="business_rule",
                statement="Eligibility precedes ordering",
            ),
        ),
    )
    store.replace_current("req-2", (_dependency("dep-3", "req-2", document_id="doc-1"),))

    assert [r.id for r in store.page(MEMBER, document_id="doc-2")] == ["dep-2"]
    assert [r.id for r in store.page(MEMBER, requirement_id="req-2")] == ["dep-3"]
    assert [r.id for r in store.page(MEMBER, target_kind="business_rule")] == ["dep-2"]
    assert [r.id for r in store.page(MEMBER, query="ELIGIBILITY")] == ["dep-2"]
    assert store.page(MEMBER, query="no such text") == ()
    # Offset and limit page the ordered rows.
    everything = store.page(MEMBER)
    assert len(everything) == 3
    assert store.page(MEMBER, offset=1, limit=1) == (everything[1],)


def test_replacing_a_requirements_rows_retires_the_previous_generation() -> None:
    store = _store(accessible={"req-1"})
    store.replace_current("req-1", (_dependency("dep-old", "req-1"),))
    store.replace_current("req-1", (_dependency("dep-new", "req-1"),))

    retired = store.get("dep-old")
    assert retired is not None and not retired.current and not retired.active
    # Only the active generation feeds the requirement's own view...
    assert [r.id for r in store.for_requirement("req-1")] == ["dep-new"]
    # ...and active_only hides the retired row from the portfolio page too.
    assert [r.id for r in store.page(MEMBER, active_only=True)] == ["dep-new"]


def test_citation_counts_count_distinct_citing_requirements_of_current_rows() -> None:
    store = _store(accessible={"req-1", "req-2"})
    store.replace_current(
        "req-1",
        (
            _dependency("dep-1", "req-1", document_id="doc-1"),
            _dependency("dep-2", "req-1", document_id="doc-1", target_kind="assumption"),
        ),
    )
    store.replace_current("req-2", (_dependency("dep-3", "req-2", document_id="doc-1"),))
    # A retired generation must not count.
    store.replace_current("req-2", ())

    assert store.citation_counts(("doc-1", "doc-unknown")) == {"doc-1": 1, "doc-unknown": 0}


def _decision(version: int) -> ImpactDecision:
    return ImpactDecision(
        dependency_id="dep-1",
        publication_state="withdrawn",
        decision=ImpactDecisionKind.RETAIN,
        reason="Historical answer still stands.",
        actor=ActorSnapshot(ActorId("owner-1"), "Amina Owner"),
        recorded_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=version,
    )


def test_decisions_append_in_order_and_refuse_a_stale_version() -> None:
    store = _store(accessible={"req-1"})
    assert store.decisions("dep-1") == ()

    store.decide(_decision(1), expected_version=0)
    store.decide(_decision(2), expected_version=1)
    assert [d.version for d in store.decisions("dep-1")] == [1, 2]

    with pytest.raises(ArtifactVersionConflictError):
        store.decide(_decision(3), expected_version=1)
