"""Catalogue suggestions survive restarts and are decided exactly once."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from smb_kernel.persistence.connector import (
    DirectPostgresConnector,
)

from smb_requirement_agent.application.ports.catalogue_candidates import ExtractionRun
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateCitation,
    CandidateContent,
    CandidateDecisionConflictError,
    CandidateKind,
    CandidateStatus,
    CatalogueCandidate,
)
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.infrastructure.persistence.postgres_catalogue_candidates import (
    PostgresCatalogueCandidates,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
NOW = datetime(2026, 9, 29, 9, 0, tzinfo=UTC)


def _candidate(release_id: str, name: str) -> CatalogueCandidate:
    return CatalogueCandidate(
        uuid4().hex,
        release_id,
        "doc-1",
        CandidateContent(CandidateKind.SYSTEM, name.casefold(), name=name),
        (CandidateCitation("paragraph 1", f"{name} is a system"),),
        "model",
        "catalogue-extraction-v1",
        NOW,
    )


def test_suggestions_round_trip_replace_undecided_ones_and_decide_once() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    store = PostgresCatalogueCandidates(DirectPostgresConnector(DATABASE_URL))
    release_id = f"draft-{uuid4().hex}"
    first, second = _candidate(release_id, "Alpha"), _candidate(release_id, "Beta")
    run = ExtractionRun(uuid4().hex, release_id, "doc-1", "model", "v1", 2, ("note",), NOW)
    store.replace_proposals(run, (first, second))

    decided = first.decide(True, "amina", NOW)
    store.save_decision(decided)
    with pytest.raises(CandidateDecisionConflictError):
        store.save_decision(decided)
    replacement = _candidate(release_id, "Gamma")
    store.replace_proposals(
        ExtractionRun(uuid4().hex, release_id, "doc-1", "model", "v1", 1, (), NOW),
        (replacement,),
    )

    reloaded = PostgresCatalogueCandidates(DirectPostgresConnector(DATABASE_URL))
    stored = {item.id: item for item in reloaded.list(release_id)}
    assert set(stored) == {first.id, replacement.id}
    assert stored[first.id].status is CandidateStatus.ACCEPTED
    assert [item.warnings for item in reloaded.runs(release_id)] == [("note",), ()]
    reloaded.reopen(first.id)
    assert reloaded.get(first.id) == first
