"""Names a document uses are matched to catalogue systems, and implied dependencies proposed.

Both stay suggestions: a maintainer confirms a match or an inferred dependency.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from smb_kernel.documents.text_extractor import SafeDocumentTextExtractor
from smb_kernel.llm.structured_output import StructuredOutputError
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.errors import ModelTransportError
from smb_requirement_agent.application.ports.architecture_rag import ArchitectureEvidenceError
from smb_requirement_agent.application.ports.catalogue_candidates import ExtractionRun
from smb_requirement_agent.application.ports.catalogue_extractor import (
    ExtractionRequest,
    ExtractionSegment,
    KnownSystem,
)
from smb_requirement_agent.application.ports.identity import Actor
from smb_requirement_agent.application.ports.system_matcher import (
    MatchableSystem,
    MatchQuery,
    MatchResult,
    SystemMatchingError,
)
from smb_requirement_agent.application.use_cases.architecture_knowledge import (
    ManageArchitectureKnowledge,
)
from smb_requirement_agent.application.use_cases.catalogue_candidates import (
    DecideCatalogueCandidate,
    ProposeCatalogueChanges,
)
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateBasis,
    CandidateCitation,
    CandidateContent,
    CandidateKind,
    CandidateStatus,
    CatalogueCandidate,
    MatchRole,
    PossibleMatch,
    find_system,
    needs_one_by_one,
    open_matches,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    InvalidKnowledgeError,
    KnowledgeDocumentVersion,
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
from smb_requirement_agent.infrastructure.llm.catalogue_extraction import (
    ChangeOutput,
    ExtractionOutput,
    FakeCatalogueExtractor,
    StructuredCatalogueExtractor,
)
from smb_requirement_agent.infrastructure.llm.catalogue_matching import (
    FakeSystemMatcher,
    MatchingOutput,
    MatchOutput,
    StructuredSystemMatcher,
    name_likeness,
    shortlists,
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

NOW = datetime(2026, 9, 30, 9, 0, tzinfo=UTC)
MAINTAINER = Actor("amina", frozenset({"knowledge_maintainer"}))
OWNER = {"X-Fake-Actor-Id": "fake-owner"}
BCRM = MatchableSystem(
    "bcrm", "BCRM", None, ("Microsoft Dynamics sales CRM", "sales CRM"), ("Assisted sales",)
)
DCRM = MatchableSystem("dcrm", "DCRM", None, ("backoffice order capture",), ("Back-office orders",))
BILLING = MatchableSystem("billing", "Billing Engine", None, (), ("Invoicing",))
SYSTEMS = (BCRM, DCRM, BILLING)
QUERY = MatchQuery("Dynamics CRM", "Quotes are prepared in Dynamics CRM.")


# Domain ---------------------------------------------------------------------------------


def test_a_system_is_found_by_its_words_when_only_one_system_fits() -> None:
    release = ArchitectureKnowledge(
        "draft",
        1,
        (
            SystemDefinition("bcrm", "BCRM", aliases=("Dynamics CRM",)),
            SystemDefinition("hub", "Order Hub"),
            SystemDefinition("hub-2", "Order-Hub 2"),
        ),
        (),
    )
    found = find_system(release, "dynamics-crm")
    assert found is not None and found.id == "bcrm"
    assert find_system(release, "ORDER_HUB") is None  # underscores are part of a word
    assert find_system(release, "---") is None
    twins = release.updated(
        systems=(*release.systems, SystemDefinition("hub-b", "Hub B", aliases=("order hub!",)))
    )
    assert find_system(twins, "order  hub") is None


def _candidate(content: CandidateContent, **values: Any) -> CatalogueCandidate:
    return CatalogueCandidate(
        "c1",
        "draft",
        "doc",
        content,
        (CandidateCitation("paragraph 1", "Order Hub sends invoices to billing"),),
        "model",
        "v1",
        NOW,
        **values,
    )


def test_only_a_dependency_can_be_inferred_and_it_must_say_why() -> None:
    link = CandidateContent(
        CandidateKind.RELATIONSHIP, "hub", target_system_id="billing", text="Sends invoices"
    )
    system = CandidateContent(CandidateKind.SYSTEM, "hub", name="Order Hub")

    inferred = _candidate(link, basis=CandidateBasis.INFERRED, rationale="It sends invoices.")
    empty = ArchitectureKnowledge("draft", 1, (), ())
    assert needs_one_by_one(inferred, empty)
    assert not needs_one_by_one(_candidate(link), empty)
    with pytest.raises(InvalidKnowledgeError, match="Only a dependency"):
        _candidate(system, basis=CandidateBasis.INFERRED, rationale="Because.")
    with pytest.raises(InvalidKnowledgeError, match="rationale"):
        _candidate(link, basis=CandidateBasis.INFERRED, rationale=" ")
    with pytest.raises(InvalidKnowledgeError, match="Only an inferred"):
        _candidate(link, rationale="Stated things need no reason.")
    matched = _candidate(
        system, possible_matches=(PossibleMatch(MatchRole.SYSTEM, "Order Hub", "dcrm", "Alike."),)
    )
    assert needs_one_by_one(matched, empty)
    known = empty.updated(systems=(SystemDefinition("dcrm", "DCRM", aliases=("Order Hub",)),))
    assert open_matches(matched, known) == ()
    dependency = _candidate(
        CandidateContent(
            CandidateKind.RELATIONSHIP, "hub", target_system_id="dynamics-crm", text="Quotes"
        ),
        possible_matches=(PossibleMatch(MatchRole.TARGET, "Dynamics CRM", "bcrm", "Alike."),),
    )
    linked = empty.updated(systems=(SystemDefinition("bcrm", "BCRM", aliases=("Dynamics CRM",)),))
    # Its source is still missing, but the name the match was for is now in the draft.
    assert open_matches(dependency, empty) == dependency.possible_matches
    assert open_matches(dependency, linked) == ()
    with pytest.raises(InvalidKnowledgeError, match="Match reason"):
        PossibleMatch(MatchRole.TARGET, "Order Hub", "dcrm", "")


# Shortlist --------------------------------------------------------------------------------


def test_name_likeness_sees_shared_words_spelling_and_abbreviations() -> None:
    assert name_likeness("Dynamics CRM", "Microsoft Dynamics sales CRM") == 1.0
    assert name_likeness("OH", "Order Hub") == 1.0
    assert name_likeness("Order Hub", "OH") == 1.0
    assert name_likeness("Billing Engin", "Billing Engine") > 0.9
    assert name_likeness("Payroll", "BCRM") < 0.5
    assert name_likeness("", "BCRM") == 0.0


def test_the_shortlist_ranks_the_likeliest_systems_and_leaves_out_unlikely_names() -> None:
    listed, warnings = shortlists((QUERY, MatchQuery("Payroll", "")), SYSTEMS, None)

    assert warnings == ()
    assert [query.written_as for query, _ in listed] == ["Dynamics CRM"]
    assert [system.id for _, system in listed[0][1]][0] == "bcrm"


class _Embeddings:
    model = "test-embedding"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        if self.fail:
            raise ArchitectureEvidenceError("down")
        # "Invoices" means the billing engine; everything else points elsewhere.
        return tuple((1.0, 0.0) if "invoic" in text.casefold() else (0.0, 1.0) for text in texts)


def test_meaning_adds_systems_names_alone_miss_and_a_silent_model_is_a_warning() -> None:
    query = MatchQuery("Invoice platform", "Invoices are issued by the invoice platform.")

    by_meaning, _ = shortlists((query,), SYSTEMS, _Embeddings())
    by_name, warnings = shortlists((query,), SYSTEMS, _Embeddings(fail=True))

    assert [system.id for _, system in by_meaning[0][1]] == ["billing"]
    assert by_name == []
    assert "by name only" in warnings[0]


# Structured matcher --------------------------------------------------------------------


class _Client:
    model = "match-model"

    def __init__(self, *outputs: MatchingOutput | Exception) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    def parse(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_type: type[Any],
        images: Sequence[tuple[str, bytes]] = (),
    ) -> Any:
        self.prompts.append(user_prompt)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output


def _matches(*items: tuple[int, str, str]) -> MatchingOutput:
    return MatchingOutput(
        matches=[MatchOutput(number=n, system_id=s, reason=r) for n, s, r in items]
    )


def test_the_model_decides_among_the_shortlist_only() -> None:
    client = _Client(
        _matches(
            (1, "bcrm", "Dynamics CRM is the sales CRM BCRM runs on."),
            (1, "billing", "Not shortlisted, so never offered."),
            (1, "dcrm", "  "),
            (7, "bcrm", "No such name was asked."),
        )
    )
    matcher = StructuredSystemMatcher(client, _Embeddings())

    result = matcher.match((QUERY,), SYSTEMS)

    assert [(item.written_as, item.system_id) for item in result.suggestions] == [
        ("Dynamics CRM", "bcrm")
    ]
    assert '"passage": "Quotes are prepared in Dynamics CRM."' in client.prompts[0]
    assert matcher.model == "match-model"
    assert matcher.prompt_version == "catalogue-matching-v1"


def test_unusable_matching_answers_are_errors_and_small_models_get_small_batches() -> None:
    with pytest.raises(SystemMatchingError):
        StructuredSystemMatcher(_Client(StructuredOutputError("bad")), _Embeddings()).match(
            (QUERY,), SYSTEMS
        )
    # A configured profile's transport fails with its own error, not a structured one;
    # it once escaped and failed a whole reading after the document was read.
    with pytest.raises(SystemMatchingError):
        StructuredSystemMatcher(
            _Client(ModelTransportError("invalid_output")), _Embeddings()
        ).match((QUERY,), SYSTEMS)
    with pytest.raises(SystemMatchingError, match="no shortlisted system"):
        StructuredSystemMatcher(_Client(_matches((1, "billing", "Wrong."))), _Embeddings()).match(
            (QUERY,), SYSTEMS
        )

    queries = tuple(MatchQuery(f"Dynamics CRM {n}", "x" * 1200) for n in range(4))
    client = _Client(*(_matches() for _ in range(4)))
    small = StructuredSystemMatcher(client, _Embeddings(), max_input_tokens=1_300)
    assert small.match(queries, SYSTEMS).suggestions == ()
    assert len(client.prompts) > 1
    # With no likely system for any name, the model is not asked at all.
    nothing = StructuredSystemMatcher(_Client(), _Embeddings(fail=True)).match(
        (MatchQuery("Payroll", ""),), SYSTEMS
    )
    assert nothing.suggestions == ()


def test_the_fake_matcher_suggests_only_close_names() -> None:
    result = FakeSystemMatcher().match((QUERY, MatchQuery("Order Hub", "")), SYSTEMS)

    assert [(item.written_as, item.system_id) for item in result.suggestions] == [
        ("Dynamics CRM", "bcrm")
    ]


# Extraction --------------------------------------------------------------------------------


class _Extraction:
    model = "read-model"

    def __init__(self, output: ExtractionOutput) -> None:
        self.output = output

    def parse(self, **_: Any) -> Any:
        return self.output


def _change(**values: Any) -> ChangeOutput:
    base: dict[str, Any] = {
        "kind": "relationship",
        "system": "Order Hub",
        "name": None,
        "name_ar": None,
        "aliases": [],
        "triggers": [],
        "target_system": "Dynamics CRM",
        "component": None,
        "technology": None,
        "domain": None,
        "parent_domain": None,
        "offering": None,
        "journey": None,
        "text": "Sends invoices",
        "evidence_numbers": [1],
        "quote": "Order Hub sends each invoice to Dynamics CRM",
        "basis": "implied",
        "reasoning": "Order Hub hands invoices to Dynamics CRM, so it relies on it.",
        "relationship_kind": None,
    }
    return ChangeOutput(**(base | values))


def test_implied_dependencies_are_inferred_with_their_reasoning_and_others_dropped() -> None:
    request = ExtractionRequest(
        "Billing flow",
        (ExtractionSegment(1, "paragraph 1", "Order Hub sends each invoice to Dynamics CRM."),),
        (KnownSystem("bcrm", "BCRM", ("sales CRM",)),),
    )
    output = ExtractionOutput(
        changes=[
            _change(),
            _change(reasoning="  "),
            _change(kind="system", name="Order Hub", target_system=None, text=None),
        ]
    )

    proposal = StructuredCatalogueExtractor(_Extraction(output), supports_images=False).propose(
        request
    )

    assert len(proposal.changes) == 1
    change = proposal.changes[0]
    assert change.basis is CandidateBasis.INFERRED
    assert change.rationale == "Order Hub hands invoices to Dynamics CRM, so it relies on it."
    assert (change.source_name, change.target_name) == ("Order Hub", "Dynamics CRM")
    assert change.content.target_system_id == "dynamics-crm"
    assert "2 suggestion(s) were left out" in proposal.warnings[0]


# Use case ---------------------------------------------------------------------------------


class _BrokenMatcher:
    model = "broken"
    prompt_version = "v0"

    def match(
        self, queries: tuple[MatchQuery, ...], systems: tuple[MatchableSystem, ...]
    ) -> MatchResult:
        raise SystemMatchingError("down")


class _NoisyMatcher(FakeSystemMatcher):
    """Offers unknown systems and repeats, which the use case must ignore."""

    def match(
        self, queries: tuple[MatchQuery, ...], systems: tuple[MatchableSystem, ...]
    ) -> MatchResult:
        found = super().match(queries, systems)
        extra = tuple(replace(item, system_id="ghost") for item in found.suggestions)
        return MatchResult(found.suggestions * 2 + extra, ("Looked by name only.",))


def _setup(
    text: bytes, matcher: Any
) -> tuple[ProposeCatalogueChanges, DecideCatalogueCandidate, ArchitectureKnowledge, Any]:
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
    proposer = ProposeCatalogueChanges(
        manage,
        storage,
        LocatedDocumentExtractor(documents),
        documents,
        FakeCatalogueExtractor(),
        matcher,
        candidates,
        FixedClock(NOW),
    )
    draft = manage.create_draft(MAINTAINER, "Next version")
    version = KnowledgeDocumentVersion(
        "doc", "Doc", "doc.txt", "text/plain", "en", "sum", "doc", "amina", NOW
    )
    storage.put(DocumentVersionId("doc"), text)
    drafted = draft.updated(documents=(version,))
    repository.save(drafted, draft.revision, "amina", "upload_document")
    return proposer, DecideCatalogueCandidate(manage, repository, candidates), drafted, candidates


def test_matching_failures_are_warnings_and_known_pairs_are_not_inferred_again() -> None:
    text = b"System: Dynamics CRM\nB2B Web sends orders to B2B BFF\n"
    proposer, _, draft, candidates = _setup(text, _BrokenMatcher())

    run = proposer.execute(draft.id, "doc", lambda: None)

    assert [item.content.kind for item in candidates.list(draft.id)] == [CandidateKind.SYSTEM]
    assert candidates.list(draft.id)[0].possible_matches == ()
    assert any("could not be checked" in warning for warning in run.warnings)
    assert any("already links those systems" in warning for warning in run.warnings)
    assert (run.match_model, run.match_prompt_version) == ("broken", "v0")


def test_unknown_or_repeated_matches_are_ignored_and_a_stated_copy_outweighs_an_inference() -> None:
    text = (
        b"System: Dynamics CRM\n"
        b"Order Hub sends invoices to BCRM\n"
        b"\n"
        b"Order Hub depends on BCRM for Sends invoices\n"
    )
    proposer, _, draft, candidates = _setup(text, _NoisyMatcher())

    run = proposer.execute(draft.id, "doc", lambda: None)

    items = {item.content.kind: item for item in candidates.list(draft.id)}
    assert [(m.system_id, m.role) for m in items[CandidateKind.SYSTEM].possible_matches] == [
        ("bcrm", MatchRole.SYSTEM)
    ]
    assert items[CandidateKind.RELATIONSHIP].basis is CandidateBasis.STATED
    assert len(items[CandidateKind.RELATIONSHIP].citations) == 2
    assert "Looked by name only." in run.warnings


def test_no_matching_runs_when_every_name_is_known() -> None:
    proposer, _, draft, _ = _setup(b"B2B Web depends on BCRM for quotes\n", FakeSystemMatcher())

    run = proposer.execute(draft.id, "doc", lambda: None)

    assert run.match_model is None


# Through the API ---------------------------------------------------------------------------

SOURCE = b"""System: Dynamics CRM
System: Order Hub
Order Hub depends on Dynamics CRM for quotes
Order Hub sends invoices to BCRM
"""


def test_a_possible_match_is_confirmed_and_inferred_items_wait_for_a_person(
    client: TestClient,
) -> None:
    draft = client.post(
        "/architecture-knowledge/releases", json={"name": "Next version"}, headers=OWNER
    ).json()
    draft = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/documents",
        data={"title": "Quotes", "language": "en", "expected_revision": draft["revision"]},
        files={"file": ("quotes.txt", SOURCE, "text/plain")},
        headers=OWNER,
    ).json()
    base = f"/architecture-knowledge/releases/{draft['id']}"
    client.post(f"{base}/documents/{draft['documents'][-1]['id']}/extractions", headers=OWNER)

    listing = client.get(f"{base}/suggestions", headers=OWNER).json()
    system = next(s for s in listing["suggestions"] if s["content"]["kind"] == "system")
    stated, inferred = sorted(
        (s for s in listing["suggestions"] if s["content"]["kind"] == "relationship"),
        key=lambda s: s["basis"] != "stated",
    )
    assert system["possible_matches"] == [
        {
            "role": "system",
            "written_as": "Dynamics CRM",
            "system_id": "bcrm",
            "system_name": "BCRM",
            "reason": "Similar name to BCRM.",
        }
    ]
    assert [(m["role"], m["system_id"]) for m in stated["possible_matches"]] == [("target", "bcrm")]
    assert inferred["basis"] == "inferred"
    assert inferred["rationale"].startswith("Order Hub sends invoices to BCRM")
    assert listing["runs"][0]["match_model"] == "fake-system-matcher"

    everything = client.post(
        f"{base}/suggestions/acceptance",
        json={"expected_revision": listing["release_revision"]},
        headers=OWNER,
    ).json()
    assert everything["remaining"] == 3
    linked = client.post(
        f"{base}/suggestions/{system['id']}/decision",
        json={
            "expected_revision": everything["release"]["revision"],
            "accept": True,
            "content": system["content"] | {"system_id": "bcrm"},
        },
        headers=OWNER,
    ).json()
    bcrm = next(item for item in linked["systems"] if item["id"] == "bcrm")
    assert "Dynamics CRM" in bcrm["aliases"]

    after = client.get(f"{base}/suggestions", headers=OWNER).json()["suggestions"]
    now_stated = next(s for s in after if s["id"] == stated["id"])
    assert (now_stated["match"], now_stated["possible_matches"]) == ("new", [])
    assert (now_stated["system_name"], now_stated["target_system_name"]) == ("Order Hub", "BCRM")
    accepted = client.post(
        f"{base}/suggestions/{stated['id']}/decision",
        json={"expected_revision": linked["revision"], "accept": True},
        headers=OWNER,
    )
    assert accepted.status_code == 200, accepted.text
    assert {
        "source_system_id": "order-hub",
        "target_system_id": "bcrm",
        "description": "quotes",
        "kind": "unspecified",
    } in accepted.json()["relationships"]
    decided = {
        s["id"]: s["status"]
        for s in client.get(f"{base}/suggestions", headers=OWNER).json()["suggestions"]
    }
    assert decided[inferred["id"]] == CandidateStatus.PROPOSED.value


def test_suggestions_and_runs_stored_before_this_change_still_load() -> None:
    stored = TypeAdapter(CatalogueCandidate).dump_python(
        _candidate(CandidateContent(CandidateKind.SYSTEM, "hub", name="Order Hub")), mode="json"
    )
    for field in ("basis", "rationale", "possible_matches"):
        stored.pop(field)
    old_run = {
        "id": "r",
        "release_id": "draft",
        "document_version_id": "doc",
        "model": "m",
        "prompt_version": "catalogue-extraction-v1",
        "candidate_count": 1,
        "warnings": [],
        "created_at": NOW.isoformat(),
    }

    loaded = TypeAdapter(CatalogueCandidate).validate_python(stored)
    assert (loaded.basis, loaded.rationale, loaded.possible_matches) == (
        CandidateBasis.STATED,
        None,
        (),
    )
    assert TypeAdapter(ExtractionRun).validate_python(old_run).match_model is None
