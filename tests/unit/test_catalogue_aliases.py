"""Every system name and alias identifies one system, even when the AI suggests otherwise.

The reported failure: accepting a suggestion that reused "BCC", an alias of
Oracle ATG BCC in the seed catalogue, for another system failed with
"Alias 'BCC' belongs to multiple systems", and Accept all failed as a whole.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.ports.catalogue_candidates import ExtractionRun
from smb_requirement_agent.application.ports.identity import Actor
from smb_requirement_agent.application.use_cases.architecture_knowledge import (
    ManageArchitectureKnowledge,
)
from smb_requirement_agent.application.use_cases.catalogue_candidates import (
    DecideCatalogueCandidate,
)
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateCitation,
    CandidateContent,
    CandidateKind,
    CandidateMatch,
    CatalogueCandidate,
    apply_candidate,
    classify,
    find_system,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    InvalidKnowledgeError,
    KnowledgeReleaseStatus,
    SystemDefinition,
)
from smb_requirement_agent.infrastructure.architecture.catalogue_files import CatalogueFileAdapter
from smb_requirement_agent.infrastructure.architecture.embeddings import FakeEmbeddings
from smb_requirement_agent.infrastructure.architecture.evidence_index import InMemoryEvidenceIndex
from smb_requirement_agent.infrastructure.architecture.knowledge_yaml import seed_knowledge
from smb_requirement_agent.infrastructure.architecture.tokenizer import FakeWordTokenizer
from smb_requirement_agent.infrastructure.persistence.in_memory_architecture_knowledge import (
    InMemoryArchitectureKnowledgeRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_catalogue_candidates import (
    InMemoryCatalogueCandidates,
)

NOW = datetime(2026, 9, 29, 9, 0, tzinfo=UTC)
MAINTAINER = Actor("amina", frozenset({"knowledge_maintainer"}))
OWNER = {"X-Fake-Actor-Id": "fake-owner"}


def _system(
    system_id: str, name: str, *aliases: str, name_ar: str | None = None
) -> CandidateContent:
    return CandidateContent(
        CandidateKind.SYSTEM, system_id, name=name, aliases=aliases, name_ar=name_ar
    )


def _draft() -> ArchitectureKnowledge:
    return replace(
        seed_knowledge(), status=KnowledgeReleaseStatus.DRAFT, published_at=None, published_by=None
    )


def _bcc(release: ArchitectureKnowledge) -> SystemDefinition:
    system = find_system(release, "BCC")
    assert system is not None
    return system


def test_a_new_system_is_added_without_an_alias_another_system_owns() -> None:
    release = _draft()
    suggestion = _system("atg-commerce", "ATG Commerce", "BCC", "Commerce", "commerce")

    assert classify(suggestion, release) is CandidateMatch.NEW
    merged = apply_candidate(suggestion, release)

    added = next(item for item in merged.systems if item.id == "atg-commerce")
    assert added.aliases == ("Commerce",)
    assert _bcc(merged).id == "oracle-atg-bcc"


def test_an_update_adds_only_free_aliases_and_skips_a_taken_arabic_name() -> None:
    release = _draft()
    arabic = "نظام الكتالوج"
    release = apply_candidate(_system("catalogue", "Catalogue", name_ar=arabic), release)
    suggestion = _system("bcrm", "BCRM", "BCC", "Dynamics CRM", name_ar=arabic)

    assert classify(suggestion, release) is CandidateMatch.UPDATES_EXISTING
    merged = apply_candidate(suggestion, release)

    bcrm = next(item for item in merged.systems if item.id == "bcrm")
    assert "Dynamics CRM" in bcrm.aliases
    assert "BCC" not in bcrm.aliases
    assert bcrm.name_ar is None
    assert _bcc(merged).id == "oracle-atg-bcc"


def test_a_suggestion_whose_only_extra_is_a_taken_alias_is_already_present() -> None:
    assert (
        classify(_system("bcrm", "BCRM", "sales CRM", "BCC"), _draft())
        is CandidateMatch.ALREADY_PRESENT
    )


def test_accept_all_leaves_what_cannot_apply_and_accepts_the_rest() -> None:
    repository = InMemoryArchitectureKnowledgeRepository(seed_knowledge())
    manage = ManageArchitectureKnowledge(
        repository,
        CatalogueFileAdapter(),
        InMemoryEvidenceIndex(FakeEmbeddings(), FakeWordTokenizer()),
        10_000,
    )
    candidates = InMemoryCatalogueCandidates()
    draft = manage.create_draft(MAINTAINER, "Next version")
    contents = (
        _system("atg-commerce", "ATG Commerce", "BCC"),
        # "BCC" and "ATG" both name Oracle ATG BCC, so it would depend on itself.
        CandidateContent(
            CandidateKind.RELATIONSHIP, "BCC", target_system_id="ATG", text="Publishes to"
        ),
        CandidateContent(CandidateKind.CONSTRAINT, "bcrm", text="Changes need a CAB slot"),
    )
    candidates.replace_proposals(
        ExtractionRun("r", draft.id, "doc", "m", "v", len(contents), (), NOW),
        tuple(
            CatalogueCandidate(
                f"c{n}",
                draft.id,
                "doc",
                content,
                (CandidateCitation("line 1", "q"),),
                "m",
                "v",
                NOW,
            )
            for n, content in enumerate(contents)
        ),
    )

    updated, remaining = DecideCatalogueCandidate(manage, repository, candidates).accept_all(
        draft.id, draft.revision, MAINTAINER, NOW
    )

    assert remaining == 1
    assert any(item.id == "atg-commerce" for item in updated.systems)
    assert (
        "Changes need a CAB slot"
        in next(item for item in updated.systems if item.id == "bcrm").constraints
    )
    assert _bcc(updated).id == "oracle-atg-bcc"


def test_a_hand_edit_that_reuses_an_alias_names_both_systems(client: TestClient) -> None:
    with pytest.raises(InvalidKnowledgeError, match="'BCC' already names Oracle ATG BCC"):
        _draft().updated(systems=(*_draft().systems, SystemDefinition("x", "X", aliases=("BCC",))))

    draft = client.post(
        "/architecture-knowledge/releases", json={"name": "Next version"}, headers=OWNER
    ).json()
    response = client.put(
        f"/architecture-knowledge/releases/{draft['id']}/systems/x",
        json={
            "expected_revision": draft["revision"],
            "system": {"id": "x", "name": "Commerce X", "aliases": ["bcc"]},
        },
        headers=OWNER,
    )

    assert response.status_code == 422
    assert "cannot also name Commerce X" in response.text
