"""Systems carry what they are for and where they sit in the landscape (ADR-0094).

The reported gap: a landscape document's Domains table, Sub-domain column and
Function column had nowhere to go. Landscape domains are a tree of their own,
apart from capability domains: a system sits in one, its capabilities may
serve several business areas.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from smb_kernel.documents.text_extractor import SafeDocumentTextExtractor

from smb_requirement_agent.application.ports.architecture_rag import EvidenceChunk
from smb_requirement_agent.application.ports.catalogue_file import CatalogueFileFormat
from smb_requirement_agent.application.ports.identity import Actor
from smb_requirement_agent.application.use_cases.architecture_index import BuildArchitectureIndex
from smb_requirement_agent.application.use_cases.architecture_knowledge import (
    ManageArchitectureKnowledge,
)
from smb_requirement_agent.domain.architecture.diff import ChangedItem, ChangeKind, diff_releases
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    InvalidKnowledgeError,
    LandscapeDomain,
    SystemDefinition,
)
from smb_requirement_agent.infrastructure.architecture.catalogue_files import CatalogueFileAdapter
from smb_requirement_agent.infrastructure.architecture.embeddings import FakeEmbeddings
from smb_requirement_agent.infrastructure.architecture.evidence_index import InMemoryEvidenceIndex
from smb_requirement_agent.infrastructure.architecture.knowledge_yaml import seed_knowledge
from smb_requirement_agent.infrastructure.architecture.located_extractor import (
    LocatedDocumentExtractor,
)
from smb_requirement_agent.infrastructure.architecture.tokenizer import ApproximateTokenizer
from smb_requirement_agent.infrastructure.persistence.in_memory_architecture_knowledge import (
    InMemoryArchitectureKnowledgeRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_document_repository import (
    InMemoryDocumentStorage,
)

OWNER = {"X-Fake-Actor-Id": "fake-owner"}
MAINTAINER = Actor("amina", frozenset({"knowledge_maintainer"}))
ADAPTER = CatalogueFileAdapter()
CUSTOMER = LandscapeDomain("customer", "Customer", description="TAM · Customer")
ASSISTED = LandscapeDomain("customer-assisted", "Assisted", parent_id="customer")
TREE = (CUSTOMER, ASSISTED)


def _placed(release: ArchitectureKnowledge) -> ArchitectureKnowledge:
    first, *rest = release.systems
    return replace(
        release,
        landscape_domains=TREE,
        systems=(
            replace(
                first,
                description="Agent screen for care and complaint management.",
                landscape_domain_id="customer-assisted",
            ),
            *rest,
        ),
    )


# Domain -----------------------------------------------------------------------------------


def test_a_system_sits_in_a_landscape_domain_the_release_lists() -> None:
    release = _placed(seed_knowledge())

    assert [item.name for item in release.landscape_path("customer-assisted")] == [
        "Customer",
        "Assisted",
    ]
    assert release.landscape_path(None) == ()
    with pytest.raises(InvalidKnowledgeError, match="placed in a landscape domain that is not"):
        replace(release, landscape_domains=(CUSTOMER,))
    with pytest.raises(InvalidKnowledgeError, match="System description must not be blank"):
        SystemDefinition("crm", "CRM", description="  ")


@pytest.mark.parametrize(
    ("tree", "message"),
    [
        ((CUSTOMER, CUSTOMER), "Landscape domain ids must be unique"),
        ((ASSISTED,), "Landscape domain 'Assisted' names a parent that is not"),
        (
            (CUSTOMER, LandscapeDomain("again", "Customer")),
            "Two landscape domains under one parent are named 'Customer'",
        ),
        (
            (
                CUSTOMER,
                ASSISTED,
                LandscapeDomain("desk", "Desk", parent_id="customer-assisted"),
                LandscapeDomain("bench", "Bench", parent_id="desk"),
            ),
            "Landscape domains are at most 3 levels deep",
        ),
    ],
)
def test_the_landscape_tree_follows_the_same_rules_as_capability_domains(
    tree: tuple[LandscapeDomain, ...], message: str
) -> None:
    with pytest.raises(InvalidKnowledgeError, match=message):
        replace(seed_knowledge(), landscape_domains=tree)


def test_landscape_and_capability_domains_are_separate_trees() -> None:
    # The same id in both trees is two different areas.
    release = replace(
        _placed(seed_knowledge()), landscape_domains=(*TREE, LandscapeDomain("billing", "Billing"))
    )

    assert {item.id for item in release.capability_domains} >= {"billing"}
    assert release.landscape_path("billing")[0].name == "Billing"


# Files ------------------------------------------------------------------------------------


@pytest.mark.parametrize("file_format", list(CatalogueFileFormat))
def test_every_format_keeps_descriptions_and_landscape_domains(
    file_format: CatalogueFileFormat,
) -> None:
    release = _placed(seed_knowledge())

    content = ADAPTER.read(file_format, ADAPTER.write(file_format, release))

    assert content.systems == release.systems
    assert content.landscape_domains == TREE


def test_a_file_placing_a_system_in_an_unlisted_landscape_domain_is_refused() -> None:
    text = b"systems:\n  - id: crm\n    name: CRM\n    landscape_domain: customer\n"

    with pytest.raises(InvalidKnowledgeError, match="crm: landscape domain 'customer' is not"):
        ADAPTER.read(CatalogueFileFormat.YAML, text)
    # A file from before landscape domains reads as it always did.
    older = ADAPTER.read(CatalogueFileFormat.YAML, b"systems:\n  - id: crm\n    name: CRM\n")
    assert older.landscape_domains == () and older.systems[0].description is None


# Diff and evidence ------------------------------------------------------------------------


def test_the_changes_view_lists_landscape_domains_and_system_placement() -> None:
    base = seed_knowledge()
    draft = _placed(base)

    found = {
        (item.item, item.change, item.key): item for item in diff_releases(base, draft).changes
    }

    first = base.systems[0].id
    assert found[(ChangedItem.SYSTEM, ChangeKind.CHANGED, first)].fields == (
        "description",
        "landscape_domain",
    )
    assert found[(ChangedItem.LANDSCAPE_DOMAIN, ChangeKind.ADDED, "customer-assisted")].label == (
        "Customer › Assisted"
    )
    renamed = replace(draft, landscape_domains=(replace(CUSTOMER, name="Clients"), ASSISTED))
    changed = diff_releases(draft, renamed).changes
    assert [(item.item, item.change, item.fields) for item in changed] == [
        (ChangedItem.LANDSCAPE_DOMAIN, ChangeKind.CHANGED, ("name",))
    ]


class _Recording(InMemoryEvidenceIndex):
    def __init__(self) -> None:
        super().__init__(FakeEmbeddings(), ApproximateTokenizer())
        self.chunks: tuple[EvidenceChunk, ...] = ()

    def store(self, release_id: str, index_id: str, chunks: tuple[EvidenceChunk, ...]) -> None:
        self.chunks = chunks
        super().store(release_id, index_id, chunks)


def _system_chunks(place: bool) -> dict[str, str]:
    repository = InMemoryArchitectureKnowledgeRepository(seed_knowledge())
    index = _Recording()
    manage = ManageArchitectureKnowledge(repository, CatalogueFileAdapter(), index, 10_000_000)
    draft = manage.create_draft(MAINTAINER, "Next version")
    if place:
        placed = _placed(draft)
        draft = manage.update(
            draft.id,
            draft.revision,
            MAINTAINER,
            systems=placed.systems,
            landscape_domains=placed.landscape_domains,
        )
    BuildArchitectureIndex(
        manage,
        index,
        InMemoryDocumentStorage(),
        LocatedDocumentExtractor(SafeDocumentTextExtractor()),
        ApproximateTokenizer(),
    ).execute(draft.id, draft.revision, "amina", fence=lambda: None)
    return {chunk.location: chunk.text for chunk in index.chunks}


def test_evidence_says_what_a_system_is_for_and_where_it_sits_only_when_known() -> None:
    first = seed_knowledge().systems[0].id
    before, after = _system_chunks(place=False), _system_chunks(place=True)

    text = after[f"system {first}"]
    assert "Agent screen for care and complaint management." in text
    assert "Landscape: Customer › Assisted" in text
    # A system with neither keeps exactly the evidence it had.
    others = [key for key in before if key.startswith("system ") and key != f"system {first}"]
    assert all(before[key] == after[key] for key in others)
    assert not any("Landscape:" in value for value in before.values())


# API --------------------------------------------------------------------------------------


def test_a_draft_saves_landscape_domains_and_keeps_them_when_a_client_leaves_them_out(
    client: TestClient,
) -> None:
    draft = client.post(
        "/architecture-knowledge/releases", json={"name": "Next version"}, headers=OWNER
    ).json()
    system = draft["systems"][0] | {
        "description": "Agent screen.",
        "landscape_domain_id": "customer-assisted",
    }
    tree = [
        {"id": "customer", "name": "Customer"},
        {"id": "customer-assisted", "name": "Assisted", "parent_id": "customer"},
    ]
    url = f"/architecture-knowledge/releases/{draft['id']}"

    saved = client.put(
        url,
        json={
            "expected_revision": draft["revision"],
            "systems": [system, *draft["systems"][1:]],
            "relationships": draft["relationships"],
            "landscape_domains": tree,
        },
        headers=OWNER,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["systems"][0]["landscape_domain_id"] == "customer-assisted"
    assert [item["id"] for item in saved.json()["landscape_domains"]] == [
        "customer",
        "customer-assisted",
    ]

    kept = client.put(
        url,
        json={
            "expected_revision": saved.json()["revision"],
            "systems": saved.json()["systems"],
            "relationships": saved.json()["relationships"],
        },
        headers=OWNER,
    ).json()
    assert len(kept["landscape_domains"]) == 2

    removed = client.put(
        url,
        json={
            "expected_revision": kept["revision"],
            "systems": kept["systems"],
            "relationships": kept["relationships"],
            "landscape_domains": [],
        },
        headers=OWNER,
    )
    assert removed.status_code == 422
    assert "landscape domain that is not in the catalogue" in removed.text
