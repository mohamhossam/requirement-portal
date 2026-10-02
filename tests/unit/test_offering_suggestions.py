"""Readings suggest whole product offerings, reviewed and accepted as one (ADR-0095).

The reported gap: a product section's facts, order types, components and
twenty-two component → system responsibilities were read and dropped.
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
    CandidateKind,
    CandidateMatch,
    CatalogueCandidate,
    apply_candidate,
    classify,
    needs_one_by_one,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    KnowledgeDocumentVersion,
    SystemDefinition,
)
from smb_requirement_agent.domain.architecture.products import (
    ComponentResponsibility,
    OfferingComponent,
    OrderType,
    ProductOffering,
    SourceConfidence,
    merge_offerings,
)
from smb_requirement_agent.domain.document.value_objects import DocumentVersionId
from smb_requirement_agent.infrastructure.architecture.catalogue_files import CatalogueFileAdapter
from smb_requirement_agent.infrastructure.architecture.catalogue_tables import (
    CatalogueTableReader,
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
    ComponentOutput,
    ExtractionOutput,
    OfferingOutput,
    OrderTypeOutput,
    ResponsibilityOutput,
    StructuredCatalogueExtractor,
)
from smb_requirement_agent.infrastructure.llm.catalogue_matching import FakeSystemMatcher
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

FIBRE = OfferingComponent(
    "fibre",
    "Fibre Access",
    responsibilities=(
        ComponentResponsibility("BCRM", "CUSTOMER_CONTEXT", "Supplies the account."),
    ),
)
OFFICE = ProductOffering(
    "office-connect",
    "Office Connect",
    code="OFFICE_CONNECT",
    order_types=(OrderType("NEW_ACTIVATION", "New Activation"),),
    components=(FIBRE,),
)


def _suggestion(offering: ProductOffering = OFFICE) -> CandidateContent:
    return CandidateContent(
        CandidateKind.PRODUCT, offering.id, name=offering.name, product=offering
    )


def _draft(*offerings: ProductOffering) -> ArchitectureKnowledge:
    return ArchitectureKnowledge(
        "draft", 1, (SystemDefinition("bcrm", "BCRM"),), (), products=offerings
    )


# Domain -----------------------------------------------------------------------------------


def test_an_offering_suggestion_waits_for_its_systems_then_names_them_by_id() -> None:
    empty = ArchitectureKnowledge("draft", 1, (), ())

    assert classify(_suggestion(), empty) is CandidateMatch.NEEDS_SYSTEM
    assert classify(_suggestion(), _draft()) is CandidateMatch.NEW
    added = apply_candidate(_suggestion(), _draft())
    # "BCRM" as the document wrote it is the draft's system "bcrm".
    assert added.products[0].components[0].responsibilities[0].system_id == "bcrm"
    assert classify(_suggestion(), added) is CandidateMatch.ALREADY_PRESENT


def test_replacing_an_offering_is_decided_one_by_one_and_keeps_its_id() -> None:
    kept = replace_offering = ProductOffering("ours", "Office Connect", code="OFFICE_CONNECT")
    draft = _draft(kept)
    candidate = CatalogueCandidate(
        "c1",
        "draft",
        "doc",
        _suggestion(),
        (CandidateCitation("line 1", "Product"),),
        "m",
        "v",
        NOW,
    )

    assert classify(candidate.content, draft) is CandidateMatch.UPDATES_EXISTING
    assert needs_one_by_one(candidate, draft)
    replaced = apply_candidate(candidate.content, draft)
    assert [item.id for item in replaced.products] == [replace_offering.id]
    assert replaced.products[0].components[0].name == "Fibre Access"


def test_two_readings_of_one_offering_merge_and_the_first_wins() -> None:
    later = ProductOffering(
        "office",
        "Office Connect",
        family="Connect",
        order_types=(OrderType("NEW_ACTIVATION", "Ignored"), OrderType("UPGRADE", "Upgrade")),
        components=(
            OfferingComponent(
                "fibre",
                "Fibre",
                kind="SERVICE",
                responsibilities=(
                    ComponentResponsibility("BCRM", "CUSTOMER_CONTEXT", "Duplicate."),
                    ComponentResponsibility("billing", "BILLING", "Bills it."),
                ),
            ),
        ),
    )

    merged = merge_offerings(OFFICE, later)

    assert (merged.id, merged.family) == ("office-connect", "Connect")
    assert [item.name for item in merged.order_types] == ["New Activation", "Upgrade"]
    (part,) = merged.components
    assert (part.name, part.kind) == ("Fibre Access", "SERVICE")
    assert [item.description for item in part.responsibilities] == [
        "Supplies the account.",
        "Bills it.",
    ]


# Reading ----------------------------------------------------------------------------------

SECTION = """## Product: Office Secure

*A fixed connection with security.*

| Code | Family | Version | Lifecycle | Evidence | Source |
|---|---|---|---|---|---|
| OFFICE_SECURE | Secure | 2.0.0 | REFERENCE | CONFIRMED | Design §1 |

### Product proposition

Office Secure adds a firewall to a fibre line.

**Product rules:** The firewall is mandatory. Static IP is locked.

### Order types

| Order type | Code | Enabled | Description | Evidence | Source |
|---|---|---|---|---|---|
| New Activation | NEW_ACTIVATION | Yes | First activation. | CONFIRMED | Design §2 |
| Upgrade | UPGRADE | No | Not modelled yet. | GAP | Design §2 |

### Customer value

| Value | Description | Evidence | Source |
|---|---|---|---|
| Secure connectivity | Firewall included. | INFERRED | Design §3 |

### Who is it for?

| Fit | Description | Evidence | Source |
|---|---|---|---|
| Branch offices | Site-based connectivity. | INFERRED | Design §3 |

### Components

| Component | Code | Type | Mandatory | Customer visible | Description | Evidence | Source |
|---|---|---|---|---|---|---|---|
| Firewall | PO_FIREWALL | SERVICE | Yes | Yes | Managed firewall. | CONFIRMED | Design §4 |
| Static IP | — | SERVICE | Yes | Yes | A fixed address. | GAP | Design §4 |

### Component → system responsibilities

| Component | System | Role | Responsibility | Order types | Evidence | Source |
|---|---|---|---|---|---|---|
| Firewall | 🔐 Security Desk | PROVISIONING | Activates it. | New Activation | CONFIRMED | §5 |
| Static IP | Order Portal | CAPTURE | Locks it. | New Activation, Migration | CONFIRMED | §5 |
"""


def _request(text: str) -> ExtractionRequest:
    segments = tuple(
        ExtractionSegment(
            number, item.location, item.text, section=item.heading_path, cells=item.cells
        )
        for number, item in enumerate(markdown_passages(text), 1)
    )
    return ExtractionRequest("Products", segments, ())


def test_a_product_section_reads_into_one_whole_offering() -> None:
    reading = CatalogueTableReader().read(_request(SECTION))

    (change,) = [item for item in reading.changes if item.content.kind is CandidateKind.PRODUCT]
    offering = change.content.product
    assert offering is not None
    assert (offering.id, offering.code, offering.family, offering.version) == (
        "office-secure",
        "OFFICE_SECURE",
        "Secure",
        "2.0.0",
    )
    assert offering.confidence is SourceConfidence.CONFIRMED
    assert offering.proposition == "Office Secure adds a firewall to a fibre line."
    assert offering.rules == ("The firewall is mandatory.", "Static IP is locked.")
    assert [(item.code, item.enabled, item.confidence) for item in offering.order_types] == [
        ("NEW_ACTIVATION", True, SourceConfidence.CONFIRMED),
        ("UPGRADE", False, SourceConfidence.GAP),
    ]
    firewall, static = offering.components
    # A component the document marks a gap is kept, marked so.
    assert (static.id, static.code, static.confidence) == ("static-ip", None, SourceConfidence.GAP)
    duty = firewall.responsibilities[0]
    assert (duty.system_id, duty.role, duty.order_types) == (
        "security-desk",
        "PROVISIONING",
        ("NEW_ACTIVATION",),
    )
    # An order type the offering does not have is left out of a responsibility.
    assert static.responsibilities[0].order_types == ("NEW_ACTIVATION",)
    assert [item.name for item in offering.values] == ["Secure connectivity"]
    assert [item.name for item in offering.audiences] == ["Branch offices"]
    assert change.locations == ("line 1",)


# The model --------------------------------------------------------------------------------


class _Answer:
    model = "scripted"

    def __init__(self, output: ExtractionOutput) -> None:
        self.output = output

    def parse(self, **_: Any) -> ExtractionOutput:
        return self.output


def _offering_change(offering: OfferingOutput) -> ChangeOutput:
    return ChangeOutput(
        kind="product_offering",
        system="",
        name="Office Connect",
        name_ar=None,
        aliases=[],
        triggers=[],
        target_system=None,
        component=None,
        technology=None,
        domain=None,
        parent_domain=None,
        offering=offering,
        text=None,
        evidence_numbers=[1],
        quote="Office Connect is a fixed connection",
        basis="stated",
        reasoning=None,
        relationship_kind=None,
        journey=None,
    )


def _duty(system: str, role: str, orders: list[str]) -> ResponsibilityOutput:
    return ResponsibilityOutput(
        system=system, role=role, description="Does it.", order_types=orders, confidence=None
    )


def test_the_models_offering_is_made_valid_before_anyone_sees_it() -> None:
    passage = "Office Connect is a fixed connection; CWOM orchestrates its fibre for new orders."
    read = OfferingOutput(
        code="OFFICE_CONNECT",
        family=None,
        version=None,
        lifecycle=None,
        proposition="A fixed connection.",
        rules=[],
        order_types=[
            OrderTypeOutput(
                name="New Activation", code=None, enabled=None, description=None, confidence=None
            ),
            OrderTypeOutput(
                name="New activation",
                code="NEW_ACTIVATION",
                enabled=None,
                description=None,
                confidence=None,
            ),
        ],
        components=[
            ComponentOutput(
                name="Fibre",
                code=None,
                type="SERVICE",
                mandatory=True,
                customer_visible=None,
                description=None,
                responsibilities=[
                    _duty("📶 CWOM", "Primary orchestrator", ["New Activation", "Migration"]),
                    _duty("CWOM", "PRIMARY_ORCHESTRATOR", []),
                ],
                confidence="confirmed",
            ),
            ComponentOutput(
                name="Fibre",
                code=None,
                type=None,
                mandatory=None,
                customer_visible=None,
                description="Read twice.",
                responsibilities=[],
                confidence=None,
            ),
        ],
        values=[],
        audiences=[],
        confidence=None,
    )
    client: Any = _Answer(ExtractionOutput(changes=[_offering_change(read)]))

    (change,) = (
        StructuredCatalogueExtractor(client, supports_images=False)
        .propose(ExtractionRequest("Notes", (ExtractionSegment(1, "paragraph 1", passage),), ()))
        .changes
    )

    offering = change.content.product
    assert offering is not None and change.content.kind is CandidateKind.PRODUCT
    assert (offering.id, offering.code) == ("office-connect", "OFFICE_CONNECT")
    assert [item.code for item in offering.order_types] == ["NEW_ACTIVATION"]
    (fibre,) = offering.components
    assert (fibre.kind, fibre.description) == ("SERVICE", "Read twice.")
    (duty,) = fibre.responsibilities
    assert (duty.system_id, duty.role, duty.order_types) == (
        "cwom",
        "PRIMARY_ORCHESTRATOR",
        ("NEW_ACTIVATION",),
    )


# Proposals --------------------------------------------------------------------------------


class _Scripted:
    supports_images = False
    model = "scripted"
    prompt_version = "v"

    def __init__(self, changes: tuple[ProposedChange, ...]) -> None:
        self.changes = changes

    def propose(self, request: ExtractionRequest) -> CatalogueProposal:
        return CatalogueProposal(self.changes, self.model, self.prompt_version)


def test_parts_of_one_offering_read_apart_are_one_suggestion() -> None:
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
        "doc", "Products", "products.md", "text/markdown", "en", "sum", "doc", "amina", NOW
    )
    storage.put(DocumentVersionId("doc"), b"# Products\n\nOffice Connect.\n")
    drafted = draft.updated(documents=(version,))
    repository.save(drafted, draft.revision, "amina", "upload_document")
    first = ProposedChange(_suggestion(), ("line 1",), "Office Connect")
    second = ProposedChange(
        _suggestion(replace_components(OFFICE, "router", "Managed Router")),
        ("line 9",),
        "Managed Router",
    )

    ProposeCatalogueChanges(
        manage,
        storage,
        LocatedDocumentExtractor(documents),
        documents,
        _Scripted((first, second)),
        FakeSystemMatcher(),
        candidates,
        FixedClock(NOW),
    ).execute(drafted.id, "doc", lambda: None)

    (suggested,) = candidates.list(drafted.id)
    assert suggested.content.product is not None
    assert [item.id for item in suggested.content.product.components] == ["fibre", "router"]
    assert [item.location for item in suggested.citations] == ["line 1", "line 9"]


def replace_components(offering: ProductOffering, part_id: str, name: str) -> ProductOffering:
    return ProductOffering(
        offering.id, offering.name, components=(OfferingComponent(part_id, name),)
    )


def test_accepting_a_landscape_document_adds_its_offering_after_its_systems(
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
    (product,) = [item for item in listing["suggestions"] if item["content"]["kind"] == "product"]
    assert product["match"] == "needs_system"

    accepted = client.post(
        f"{base}/suggestions/acceptance",
        json={"expected_revision": listing["release_revision"]},
        headers=OWNER,
    ).json()

    (offering,) = accepted["release"]["products"]
    assert offering["id"] == "office-connect"
    duties = {
        (part["name"], duty["system_id"], duty["role"])
        for part in offering["components"]
        for duty in part["responsibilities"]
    }
    assert duties == {
        ("Fibre Access", "flow-engine", "PRIMARY_ORCHESTRATOR"),
        ("Managed Router", "field-desk", "FIELD_FULFILLMENT"),
    }
