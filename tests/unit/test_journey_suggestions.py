"""Readings suggest whole journeys, reviewed and accepted as one (ADR-0096).

The reported gap: a journey section's eighteen activities, seven flow rules,
eighteen integrations and the details under each activity were read only as
dependencies, or not at all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

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
    CandidateCitation,
    CandidateContent,
    CandidateDependencyError,
    CandidateKind,
    CandidateMatch,
    CatalogueCandidate,
    apply_candidate,
    classify,
    needs_one_by_one,
)
from smb_requirement_agent.domain.architecture.journeys import (
    Activity,
    FlowRule,
    FlowRuleKind,
    Journey,
    journey_edges,
    merge_journeys,
    same_journey,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    KnowledgeDocumentVersion,
    SystemDefinition,
)
from smb_requirement_agent.domain.architecture.products import (
    OfferingComponent,
    OrderType,
    ProductOffering,
    SourceConfidence,
    find_offering,
    find_order_type,
)
from smb_requirement_agent.domain.document.value_objects import DocumentVersionId
from smb_requirement_agent.infrastructure.architecture.catalogue_files import CatalogueFileAdapter
from smb_requirement_agent.infrastructure.architecture.catalogue_tables import (
    CatalogueTableReader,
    TableFirstCatalogueExtractor,
)
from smb_requirement_agent.infrastructure.architecture.embeddings import FakeEmbeddings
from smb_requirement_agent.infrastructure.architecture.evidence_index import InMemoryEvidenceIndex
from smb_requirement_agent.infrastructure.architecture.knowledge_yaml import seed_knowledge
from smb_requirement_agent.infrastructure.architecture.located_extractor import (
    LocatedDocumentExtractor,
)
from smb_requirement_agent.infrastructure.architecture.markdown_passages import markdown_passages
from smb_requirement_agent.infrastructure.architecture.tokenizer import FakeWordTokenizer
from smb_requirement_agent.infrastructure.documents.text_extractor import SafeDocumentTextExtractor
from smb_requirement_agent.infrastructure.llm.catalogue_extraction import (
    ChangeOutput,
    ExtractionOutput,
    JourneyOutput,
    LeanExtractionOutput,
    RuleOutput,
    StepOutput,
    StructuredCatalogueExtractor,
)
from smb_requirement_agent.infrastructure.llm.catalogue_matching import FakeSystemMatcher
from smb_requirement_agent.infrastructure.llm.prompts.catalogue_extraction_prompt import (
    JOURNEY_RULE,
    LEAN_SYSTEM_PROMPT,
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

FIXTURE = Path(__file__).parent.parent / "fixtures" / "catalogue" / "synthetic_landscape.md"
OWNER = {"X-Fake-Actor-Id": "fake-owner"}
MAINTAINER = Actor("amina", frozenset({"knowledge_maintainer"}))
NOW = datetime(2026, 10, 1, tzinfo=UTC)

OFFICE = ProductOffering(
    "office-connect",
    "Office Connect",
    code="OFFICE_CONNECT",
    order_types=(OrderType("NEW_ACTIVATION", "New Activation"),),
    components=(OfferingComponent("po-fibre", "Fibre Access", code="PO_FIBRE"),),
)
# As a reading names things: systems and the component as the document writes them.
ACTIVATION = Journey(
    "office-connect-new-activation",
    "New Activation",
    product_id="Office Connect",
    order_type_code="New Activation",
    activities=(
        Activity("10", "Place order", performing_system_id="Order Portal"),
        Activity(
            "20",
            "Validate order",
            performing_system_id="Flow Engine",
            supporting_system_ids=("Order Portal",),
            component_ids=("Fibre Access",),
        ),
    ),
)
SYSTEMS = (
    SystemDefinition("order-portal", "Order Portal"),
    SystemDefinition("flow-engine", "Flow Engine"),
)


def _suggestion(journey: Journey = ACTIVATION) -> CandidateContent:
    return CandidateContent(CandidateKind.JOURNEY, journey.id, name=journey.name, journey=journey)


def _draft(
    systems: tuple[SystemDefinition, ...] = SYSTEMS,
    offerings: tuple[ProductOffering, ...] = (OFFICE,),
    journeys: tuple[Journey, ...] = (),
) -> ArchitectureKnowledge:
    return ArchitectureKnowledge("draft", 1, systems, (), products=offerings, journeys=journeys)


def _request(text: str) -> ExtractionRequest:
    segments = tuple(
        ExtractionSegment(
            number, item.location, item.text, section=item.heading_path, cells=item.cells
        )
        for number, item in enumerate(markdown_passages(text), 1)
    )
    return ExtractionRequest("Journeys", segments, ())


# Domain -----------------------------------------------------------------------------------


def test_a_journey_waits_for_its_systems_and_offering_then_names_them_by_id() -> None:
    assert classify(_suggestion(), _draft(systems=())) is CandidateMatch.NEEDS_SYSTEM
    assert classify(_suggestion(), _draft(offerings=())) is CandidateMatch.NEEDS_OFFERING
    wrong_order = Journey(
        ACTIVATION.id, ACTIVATION.name, product_id="Office Connect", order_type_code="Upgrade"
    )
    assert classify(_suggestion(wrong_order), _draft()) is CandidateMatch.NEEDS_OFFERING
    bare = ProductOffering("office-connect", "Office Connect", order_types=OFFICE.order_types)
    assert classify(_suggestion(), _draft(offerings=(bare,))) is CandidateMatch.NEEDS_COMPONENT
    try:
        apply_candidate(_suggestion(), _draft(offerings=()))
    except CandidateDependencyError as exc:
        assert "product offering 'Office Connect'" in str(exc)
    else:  # pragma: no cover - the journey must wait
        raise AssertionError("A journey was accepted before its offering.")

    assert classify(_suggestion(), _draft()) is CandidateMatch.NEW
    added = apply_candidate(_suggestion(), _draft())

    (journey,) = added.journeys
    # Names as the document wrote them become the draft's ids and codes.
    assert (journey.product_id, journey.order_type_code) == ("office-connect", "NEW_ACTIVATION")
    validate = journey.ordered[1]
    assert (validate.performing_system_id, validate.supporting_system_ids) == (
        "flow-engine",
        ("order-portal",),
    )
    assert validate.component_ids == ("po-fibre",)
    assert classify(_suggestion(), added) is CandidateMatch.ALREADY_PRESENT


def test_replacing_a_journey_is_decided_one_by_one_and_keeps_its_id() -> None:
    ours = Journey(
        "ours",
        "New Activation",
        product_id="office-connect",
        activities=(Activity("10", "Place order", performing_system_id="order-portal"),),
    )
    draft = _draft(journeys=(ours,))
    candidate = CatalogueCandidate(
        "c1",
        "draft",
        "doc",
        _suggestion(),
        (CandidateCitation("line 1", "Journey: New Activation"),),
        "m",
        "v",
        NOW,
    )

    assert classify(candidate.content, draft) is CandidateMatch.UPDATES_EXISTING
    assert needs_one_by_one(candidate, draft)
    replaced = apply_candidate(candidate.content, draft)
    assert [item.id for item in replaced.journeys] == ["ours"]
    assert len(replaced.journeys[0].activities) == 2


def test_two_readings_of_one_journey_merge_and_the_first_wins() -> None:
    later = Journey(
        "other",
        "New Activation",
        product_id="office-connect",
        order_type_code="NEW_ACTIVATION",
        activities=(
            Activity("10", "Ignored", performing_system_id="x", input="Basket"),
            Activity("30", "Install router", track="FIELD"),
        ),
        flow_rules=(FlowRule(FlowRuleKind.PARALLEL, "10", "30", rejoin_at="10"),),
    )
    first = Journey(
        "first",
        "New Activation",
        activities=(Activity("10", "Place order", performing_system_id="order-portal"),),
    )

    merged = merge_journeys(first, later)

    assert (merged.id, merged.product_id, merged.order_type_code) == (
        "first",
        "office-connect",
        "NEW_ACTIVATION",
    )
    place, install = merged.ordered
    assert (place.name, place.performing_system_id, place.input) == (
        "Place order",
        "order-portal",
        "Basket",
    )
    assert install.track == "FIELD" and len(merged.flow_rules) == 1
    # One name for two offerings is two journeys.
    assert not same_journey(
        Journey("a", "New Activation", product_id="office-connect"),
        Journey("b", "New Activation", product_id="office-secure"),
    )
    assert same_journey(first, later)


def test_an_offering_and_its_parts_are_found_by_code_or_name() -> None:
    assert find_offering((OFFICE,), "office connect") is OFFICE
    assert find_offering((OFFICE,), "OFFICE_CONNECT") is OFFICE
    assert find_offering((OFFICE,), "Office Secure") is None
    assert find_order_type(OFFICE, "new activation") is OFFICE.order_types[0]


# The table reader -------------------------------------------------------------------------


def test_a_journey_section_reads_into_one_whole_journey() -> None:
    reading = CatalogueTableReader().read(_request(FIXTURE.read_text(encoding="utf-8")))

    (change,) = [item for item in reading.changes if item.content.kind is CandidateKind.JOURNEY]
    journey = change.content.journey
    assert journey is not None
    assert (journey.id, journey.name, journey.product_id) == (
        "office-connect-new-activation",
        "New Activation",
        "office-connect",
    )
    assert [item.number for item in journey.ordered] == ["10", "20", "25", "30", "40"]
    validate = journey.ordered[1]
    assert (validate.performing_system_id, validate.supporting_system_ids, validate.mode) == (
        "flow-engine",
        ("pricing-engine",),
        "AUTOMATED",
    )
    # Its details: the description, the offering's components by id, input and output,
    # eTOM, and the evidence's source.
    assert validate.description == "Check the basket against the offer's rules before it is routed."
    assert validate.component_ids == ("po-fibre", "po-router")
    assert (validate.input, validate.output) == ("Basket", "Validated order")
    assert validate.etom == "Customer Relationship Management › Order Handling"
    assert (validate.confidence, validate.source) == (
        SourceConfidence.CONFIRMED,
        "Synthetic design §5",
    )
    # An activity only its details describe is still one, from its heading.
    close = journey.ordered[-1]
    assert (close.name, close.track, close.performing_system_id, close.confidence) == (
        "Close order",
        "MAIN",
        "notifier",
        SourceConfidence.INFERRED,
    )
    assert [(item.from_activity, item.to_activity) for item in journey.integrations] == [
        ("10", "20"),
        ("20", "25"),
        ("25", "30"),
    ]
    assert [
        (edge.from_activity, edge.to_activity, edge.label) for edge in journey_edges(journey)
    ] == [
        ("10", "20", None),
        ("20", "25", None),
        ("25", "40", "PASS"),
        ("25", "10", "FAIL"),
        ("25", "30", "FIELD"),
        ("30", "40", "rejoin"),
    ]
    assert change.locations == ("line 60",)
    sent = {item.number: item for item in _request(FIXTURE.read_text(encoding="utf-8")).segments}
    taken = {sent[number].text.splitlines()[0] for number in reading.consumed}
    # The drawn flow and the detail bullets are taken whole; activity rows and
    # descriptions still go to the model, for capabilities and constraints.
    assert "```mermaid" in taken and "- **Phase / track:** VALIDATION / MAIN" in taken
    assert {sent[number].text for number in reading.read} >= {
        "Tell the customer the order is complete."
    }


SECTION = """\
# Offers

## Product: Office Secure

| Order type | Code | Enabled |
|---|---|---|
| New Activation | NEW_ACTIVATION | Yes |

### Journey: New Activation

| # | Activity | Performing system | Evidence |
|---|---|---|---|
| 10 | Place order | 🌐 Order Portal | CONFIRMED |
| 20 | Validate order | Flow Engine / Rule Desk | CONFIRMED |

## Journey: Repair

| # | Activity | Performing system |
|---|---|---|
| 10 | Log fault | Order Portal |

| Rule type | From | To |
|---|---|---|
| LOOP | 10 | 90 |
"""


def test_a_journey_finds_its_offering_and_order_type_or_is_left_to_the_model() -> None:
    reading = CatalogueTableReader().read(_request(SECTION))

    (change,) = [item for item in reading.changes if item.content.kind is CandidateKind.JOURNEY]
    journey = change.content.journey
    assert journey is not None
    # Inside the product's section, its order type is the one of the journey's name.
    assert (journey.product_id, journey.order_type_code) == ("office-secure", "NEW_ACTIVATION")
    # "A / B" naming no one system is two; an emoji is styling.
    assert journey.ordered[0].performing_system_id == "order-portal"
    assert journey.ordered[1].performing_system_id == "flow-engine"
    # A rule naming an activity the journey lacks: the journey is not suggested, and its
    # rows stay with the model.
    assert reading.notes == [
        "The journey Repair could not be read: Repair: a loop rule names activity '90', "
        "which is not in the journey."
    ]
    repair = [item for item in _request(SECTION).segments if "Repair" in " ".join(item.section)]
    assert not {item.number for item in repair} & (reading.consumed | reading.read)


# The model --------------------------------------------------------------------------------


class _Answer:
    model = "scripted"

    def __init__(self, output: ExtractionOutput) -> None:
        self.output = output
        self.asked: list[tuple[str, type[Any]]] = []

    def parse(self, *, system_prompt: str, schema_type: type[Any], **_: Any) -> Any:
        self.asked.append((system_prompt, schema_type))
        if schema_type is LeanExtractionOutput:
            return LeanExtractionOutput.model_validate(
                {"changes": [item.model_dump(exclude={"journey"}) for item in self.output.changes]}
            )
        return self.output


def _journey_change(journey: JourneyOutput | None, quote: str) -> ChangeOutput:
    return ChangeOutput(
        kind="journey",
        system="",
        name="New Activation",
        name_ar=None,
        aliases=[],
        triggers=[],
        target_system=None,
        component=None,
        technology=None,
        domain=None,
        parent_domain=None,
        offering=None,
        text=None,
        evidence_numbers=[1],
        quote=quote,
        basis="stated",
        reasoning=None,
        relationship_kind=None,
        journey=journey,
    )


def _step(number: str, name: str, system: str | None = None) -> StepOutput:
    return StepOutput(
        number=number, name=name, track=None, system=system, supporting=[], function=None
    )


PASSAGE = "The New Activation journey: the Order Portal takes it; the Flow Engine validates it."


def test_the_models_journey_is_made_valid_before_anyone_sees_it() -> None:
    read = JourneyOutput(
        product="Office Connect",
        order_type="New Activation",
        steps=[
            _step("10", "Place order", "🌐 Order Portal"),
            _step("10", "Read twice"),
            _step("20", "Validate order", "Flow Engine"),
        ],
        rules=[
            RuleOutput(
                kind="loop", from_step="20", to_step="10", condition="Rejected", rejoin=None
            ),
            RuleOutput(kind="decision", from_step="20", to_step="99", condition=None, rejoin=None),
        ],
    )
    client: Any = _Answer(ExtractionOutput(changes=[_journey_change(read, PASSAGE[:40])]))

    proposal = StructuredCatalogueExtractor(client, supports_images=False).propose(
        ExtractionRequest("Notes", (ExtractionSegment(1, "paragraph 1", PASSAGE),), ())
    )

    (change,) = proposal.changes
    journey = change.content.journey
    assert journey is not None and change.content.kind is CandidateKind.JOURNEY
    assert (journey.id, journey.product_id, journey.order_type_code) == (
        "office-connect-new-activation",
        "Office Connect",
        "New Activation",
    )
    assert [(item.number, item.name, item.performing_system_id) for item in journey.ordered] == [
        ("10", "Place order", "order-portal"),
        ("20", "Validate order", "flow-engine"),
    ]
    # A rule to an activity the journey does not have is left out.
    assert [(rule.kind, rule.to_activity, rule.condition) for rule in journey.flow_rules] == [
        (FlowRuleKind.LOOP, "10", "Rejected")
    ]
    assert client.asked == [(SYSTEM_PROMPT, ExtractionOutput)]


def test_a_small_context_reads_without_journeys_and_says_so() -> None:
    client: Any = _Answer(ExtractionOutput(changes=[]))
    request = ExtractionRequest("Notes", (ExtractionSegment(1, "paragraph 1", PASSAGE),), ())

    # An 8k local model with half kept for its answer: a journey's answer shape would leave
    # it too little room for the document, so it is asked without one.
    proposal = StructuredCatalogueExtractor(
        client, supports_images=False, max_input_tokens=8192 - 4096
    ).propose(request)

    assert client.asked == [(LEAN_SYSTEM_PROMPT, LeanExtractionOutput)]
    assert JOURNEY_RULE not in LEAN_SYSTEM_PROMPT and JOURNEY_RULE in SYSTEM_PROMPT
    assert proposal.warnings[0] == (
        "This model's context is too small to also propose journeys from prose; journeys set "
        "out in tables are still read."
    )
    # A context with room asks for journeys.
    roomy: Any = _Answer(ExtractionOutput(changes=[]))
    StructuredCatalogueExtractor(roomy, supports_images=False, max_input_tokens=32_000).propose(
        request
    )
    assert roomy.asked == [(SYSTEM_PROMPT, ExtractionOutput)]


def test_a_journey_the_tables_gave_is_not_repeated_from_its_read_rows() -> None:
    class _Model:
        supports_images = False
        model = "scripted"
        prompt_version = "v"

        def propose(self, request: ExtractionRequest) -> CatalogueProposal:
            row = next(item for item in request.segments if item.text.startswith("#: 10"))
            assert row.read
            repeated = ProposedChange(_suggestion(), (row.location,), row.text)
            return CatalogueProposal((repeated,), self.model, self.prompt_version)

    proposal = TableFirstCatalogueExtractor(_Model(), CatalogueTableReader()).propose(
        _request(FIXTURE.read_text(encoding="utf-8"))
    )

    journeys = [item for item in proposal.changes if item.content.kind is CandidateKind.JOURNEY]
    assert [item.reader is not None for item in journeys] == [True]


# Proposals --------------------------------------------------------------------------------


class _Scripted:
    supports_images = False
    model = "scripted"
    prompt_version = "v"

    def __init__(self, changes: tuple[ProposedChange, ...]) -> None:
        self.changes = changes

    def propose(self, request: ExtractionRequest) -> CatalogueProposal:
        return CatalogueProposal(self.changes, self.model, self.prompt_version)


def test_a_journey_read_in_parts_is_one_suggestion_naming_the_suggested_offering() -> None:
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
        "doc", "Journeys", "journeys.md", "text/markdown", "en", "sum", "doc", "amina", NOW
    )
    storage.put(DocumentVersionId("doc"), b"# Journeys\n\nNew Activation.\n")
    drafted = draft.updated(documents=(version,))
    repository.save(drafted, draft.revision, "amina", "upload_document")
    offering = ProposedChange(
        CandidateContent(CandidateKind.PRODUCT, OFFICE.id, name=OFFICE.name, product=OFFICE),
        ("line 1",),
        "Office Connect",
    )
    later = Journey(
        "new-activation",
        "New Activation",
        product_id="OFFICE_CONNECT",
        activities=(Activity("30", "Install router"),),
    )
    first = ProposedChange(_suggestion(), ("line 5",), "New Activation")
    second = ProposedChange(_suggestion(later), ("line 9",), "Install router")

    ProposeCatalogueChanges(
        manage,
        storage,
        LocatedDocumentExtractor(documents),
        documents,
        _Scripted((offering, first, second)),
        FakeSystemMatcher(),
        candidates,
        FixedClock(NOW),
    ).execute(drafted.id, "doc", lambda: None)

    (suggested,) = [
        item for item in candidates.list(drafted.id) if item.content.kind is CandidateKind.JOURNEY
    ]
    journey = suggested.content.journey
    assert journey is not None
    # Written "Office Connect" and "OFFICE_CONNECT", both name the suggested offering.
    assert (journey.product_id, journey.order_type_code) == ("office-connect", "NEW_ACTIVATION")
    assert [item.number for item in journey.ordered] == ["10", "20", "30"]
    assert journey.ordered[1].component_ids == ("po-fibre",)
    assert [item.location for item in suggested.citations] == ["line 5", "line 9"]


def test_accepting_a_landscape_document_adds_its_journey_after_its_offering(
    client: TestClient,
) -> None:
    draft = client.post(
        "/architecture-knowledge/releases", json={"name": "Next version"}, headers=OWNER
    ).json()
    uploaded = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/documents",
        data={"title": "Landscape", "language": "en", "expected_revision": draft["revision"]},
        files={"file": ("landscape.md", FIXTURE.read_bytes(), "text/markdown")},
        headers=OWNER,
    ).json()
    base = f"/architecture-knowledge/releases/{draft['id']}"
    client.post(f"{base}/documents/{uploaded['documents'][-1]['id']}/extractions", headers=OWNER)
    listing = client.get(f"{base}/suggestions", headers=OWNER).json()
    (suggested,) = [item for item in listing["suggestions"] if item["content"]["kind"] == "journey"]
    assert suggested["match"] == "needs_system"
    assert len(suggested["content"]["journey"]["edges"]) == 6

    accepted = client.post(
        f"{base}/suggestions/acceptance",
        json={"expected_revision": listing["release_revision"]},
        headers=OWNER,
    ).json()

    (journey,) = accepted["release"]["journeys"]
    assert (journey["product_id"], journey["name"]) == ("office-connect", "New Activation")
    assert [item["performing_system_id"] for item in journey["activities"]] == [
        "order-portal",
        "flow-engine",
        "flow-engine",
        "field-desk",
        "notifier",
    ]
    assert len(journey["edges"]) == 6
