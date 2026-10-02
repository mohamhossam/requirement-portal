"""A landscape's tables read as records: plain names, stated integrations, one id per system.

The reported failure: system names kept their emoji, "CRM GW" and "CBCM / CRMGW"
became two systems, the same integration was suggested from both ends, and
integration-table rows were offered only as inferences to decide one by one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from smb_requirement_agent.application.ports.catalogue_extractor import (
    CatalogueProposal,
    ExtractionRequest,
    ExtractionSegment,
    ProposedChange,
)
from smb_requirement_agent.application.ports.identity import Actor
from smb_requirement_agent.application.use_cases.architecture_knowledge import (
    ManageArchitectureKnowledge,
)
from smb_requirement_agent.application.use_cases.catalogue_candidates import (
    ProposeCatalogueChanges,
)
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateBasis,
    CandidateContent,
    CandidateKind,
    find_system,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    KnowledgeDocumentVersion,
    RelationshipKind,
    SystemDefinition,
)
from smb_requirement_agent.domain.document.value_objects import DocumentVersionId
from smb_requirement_agent.infrastructure.architecture.catalogue_files import CatalogueFileAdapter
from smb_requirement_agent.infrastructure.architecture.embeddings import FakeEmbeddings
from smb_requirement_agent.infrastructure.architecture.evidence_index import InMemoryEvidenceIndex
from smb_requirement_agent.infrastructure.architecture.knowledge_yaml import seed_knowledge
from smb_requirement_agent.infrastructure.architecture.located_extractor import (
    LocatedDocumentExtractor,
)
from smb_requirement_agent.infrastructure.architecture.tokenizer import FakeWordTokenizer
from smb_requirement_agent.infrastructure.documents.text_extractor import SafeDocumentTextExtractor
from smb_requirement_agent.infrastructure.llm.catalogue_extraction import (
    ChangeOutput,
    ExtractionOutput,
    StructuredCatalogueExtractor,
    plain_name,
)
from smb_requirement_agent.infrastructure.llm.catalogue_matching import FakeSystemMatcher
from smb_requirement_agent.infrastructure.llm.prompts.catalogue_extraction_prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_architecture_knowledge import (
    InMemoryArchitectureKnowledgeRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_catalogue_candidates import (
    InMemoryCatalogueCandidates,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_document_repository import (
    InMemoryDocumentStorage,
)
from smb_requirement_agent.infrastructure.time.fixed_clock import FixedClock

NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
MAINTAINER = Actor("amina", frozenset({"knowledge_maintainer"}))
ROW = "System: 🧾 Order Gateway | ID: SYS-GATEWAY | Integrations: Flow Engine, ORDER GW"


# Names ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("written", "plain"),
    [
        ("📈 BCRM", "BCRM"),
        ("🛠️ WFM / Remedy", "WFM / Remedy"),
        ("🖥️ SaS Self-Service Portal", "SaS Self-Service Portal"),
        ("👩🏽‍💻 Agent Desk", "Agent Desk"),
        ("1️⃣ First Line", "1 First Line"),
        ("C^ Engine (v2)", "C^ Engine (v2)"),
        ("نظام الفوترة", "نظام الفوترة"),
    ],
)
def test_a_system_name_loses_its_decoration_and_nothing_else(written: str, plain: str) -> None:
    assert plain_name(written) == plain


class _Answer:
    model = "scripted"

    def __init__(self, output: ExtractionOutput) -> None:
        self.output = output

    def parse(self, **_: Any) -> ExtractionOutput:
        return self.output


def _change(**values: Any) -> ChangeOutput:
    base: dict[str, Any] = {
        "kind": "system",
        "system": "🧾 Order Gateway",
        "name": "🧾 Order Gateway",
        "name_ar": None,
        "aliases": ["SYS-GATEWAY"],
        "triggers": [],
        "target_system": None,
        "component": None,
        "technology": None,
        "domain": None,
        "parent_domain": None,
        "offering": None,
        "journey": None,
        "text": None,
        "evidence_numbers": [1],
        "quote": ROW,
        "basis": "stated",
        "reasoning": None,
        "relationship_kind": None,
    }
    return ChangeOutput(**(base | values))


def test_names_the_model_copies_with_their_emoji_become_plain_ids_and_names() -> None:
    output = ExtractionOutput(
        changes=[
            _change(),
            _change(
                kind="relationship",
                name=None,
                aliases=[],
                target_system="🔄 Flow Engine",
                text="Integrates with Flow Engine",
            ),
        ]
    )
    request = ExtractionRequest("Landscape", (ExtractionSegment(1, "line 7", ROW),), ())
    client: Any = _Answer(output)

    system, link = (
        StructuredCatalogueExtractor(client, supports_images=False).propose(request).changes
    )

    assert (system.content.system_id, system.content.name) == ("order-gateway", "Order Gateway")
    assert system.content.aliases == ("SYS-GATEWAY",)
    assert (link.content.system_id, link.content.target_system_id) == (
        "order-gateway",
        "flow-engine",
    )
    assert (link.source_name, link.target_name) == ("Order Gateway", "Flow Engine")
    # The quote stays the document's own words.
    assert system.quote == ROW


def test_a_name_written_apart_finds_the_system_whose_alias_runs_it_together() -> None:
    systems = (
        SystemDefinition("order-gateway", "Order Gateway", ("ORDERGW",)),
        SystemDefinition("order-archive", "Order Archive"),
    )
    release = ArchitectureKnowledge("k", 1, systems, ())

    assert (found := find_system(release, "ORDER GW")) is not None and found.id == "order-gateway"
    # Two systems that both run together to the same letters answer to neither.
    twice = ArchitectureKnowledge(
        "k", 1, (*systems, SystemDefinition("other", "Other", ("ORD ERGW",))), ()
    )
    assert find_system(twice, "ORDER GW") is None


def test_the_prompt_reads_tables_as_records_and_integrations_as_stated() -> None:
    assert PROMPT_VERSION == "catalogue-extraction-v10"
    for rule in (
        "Read each row as one record",
        "the ID value",
        "Each entry of that row's Integrations is a stated relationship",
        "Never add the reverse",
        '"A / B" names two systems',
        "Ignore Owner columns",
        "Supporting systems listed on the row are not dependencies",
        "Leave out a row the document marks GAP",
    ):
        assert rule in SYSTEM_PROMPT
    assert "a row of an integration table" not in SYSTEM_PROMPT


# Proposals --------------------------------------------------------------------------------


class _Scripted:
    supports_images = False
    model = "scripted"
    prompt_version = PROMPT_VERSION

    def __init__(self, changes: tuple[ProposedChange, ...]) -> None:
        self.changes = changes

    def propose(self, request: ExtractionRequest) -> CatalogueProposal:
        return CatalogueProposal(self.changes, self.model, self.prompt_version)


def _system(system_id: str, name: str, *aliases: str) -> ProposedChange:
    return ProposedChange(
        CandidateContent(CandidateKind.SYSTEM, system_id, name=name, aliases=aliases),
        (f"line {len(name)}",),
        name,
        source_name=name,
    )


def _link(
    source: str,
    target: str,
    location: str,
    kind: RelationshipKind = RelationshipKind.UNSPECIFIED,
) -> ProposedChange:
    return ProposedChange(
        CandidateContent(
            CandidateKind.RELATIONSHIP,
            source,
            target_system_id=target,
            text=f"Integrates with {target}",
            relationship_kind=kind,
        ),
        (location,),
        f"Integrations: {target}",
        source_name=source,
        target_name=target,
    )


def _propose(
    *changes: ProposedChange,
) -> tuple[Any, ArchitectureKnowledge, InMemoryCatalogueCandidates]:
    repository = InMemoryArchitectureKnowledgeRepository(seed_knowledge())
    manage = ManageArchitectureKnowledge(
        repository,
        CatalogueFileAdapter(),
        InMemoryEvidenceIndex(FakeEmbeddings(), FakeWordTokenizer()),
        10_000,
    )
    storage = InMemoryDocumentStorage()
    candidates = InMemoryCatalogueCandidates()
    documents = SafeDocumentTextExtractor()
    draft = manage.create_draft(MAINTAINER, "Next version")
    version = KnowledgeDocumentVersion(
        "doc", "Landscape", "landscape.md", "text/markdown", "en", "sum", "doc", "amina", NOW
    )
    storage.put(DocumentVersionId("doc"), b"# Landscape\n\nSystems and their integrations.\n")
    drafted = draft.updated(documents=(version,))
    repository.save(drafted, draft.revision, "amina", "upload_document")
    run = ProposeCatalogueChanges(
        manage,
        storage,
        LocatedDocumentExtractor(documents),
        documents,
        _Scripted(changes),
        FakeSystemMatcher(),
        candidates,
        FixedClock(NOW),
    ).execute(drafted.id, "doc", lambda: None)
    return run, drafted, candidates


def _links(candidates: InMemoryCatalogueCandidates, release_id: str) -> list[Any]:
    return [
        item
        for item in candidates.list(release_id)
        if item.content.kind is CandidateKind.RELATIONSHIP
    ]


def test_every_name_a_document_uses_for_one_system_becomes_that_systems_id() -> None:
    """Read in separate calls, "ORDER GW" was slugged to a system nobody suggested."""
    run, draft, candidates = _propose(
        _system("order-gateway", "Order Gateway", "ORDERGW", "SYS-GATEWAY"),
        _system("flow-engine", "Flow Engine"),
        _link("flow-engine", "order-gw", "line 9"),
        _link("sys-gateway", "sys-gateway", "line 8"),
    )

    (link,) = _links(candidates, draft.id)
    assert (link.content.system_id, link.content.target_system_id) == (
        "flow-engine",
        "order-gateway",
    )
    # A system named by its ID on both ends was a link to itself, so it is left out.
    assert any("linked a system to itself" in warning for warning in run.warnings)


def test_a_link_listed_from_both_systems_is_one_suggestion_unless_each_says_how() -> None:
    run, draft, candidates = _propose(
        _system("order-gateway", "Order Gateway"),
        _system("flow-engine", "Flow Engine"),
        _link("order-gateway", "flow-engine", "line 7"),
        _link("flow-engine", "order-gateway", "line 9"),
    )

    (link,) = _links(candidates, draft.id)
    assert [citation.location for citation in link.citations] == ["line 7", "line 9"]
    assert link.basis is CandidateBasis.STATED
    assert (
        "1 dependency suggestion(s) listed from both systems were merged into one." in run.warnings
    )

    _, typed_draft, typed = _propose(
        _system("order-gateway", "Order Gateway"),
        _system("flow-engine", "Flow Engine"),
        _link("order-gateway", "flow-engine", "line 7", RelationshipKind.CALLS_API),
        _link("flow-engine", "order-gateway", "line 9"),
    )
    assert len(_links(typed, typed_draft.id)) == 2
