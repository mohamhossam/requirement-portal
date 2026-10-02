"""Product offerings and journeys around an impact, as advice for a reviewer (ADR-0097).

The reported gap: an item about "Business Pro Plus" mapped to systems without
saying which systems the catalogue makes responsible for that offering, or
where in its journey a mapped system acts and who hands over to and from it.
"""

from __future__ import annotations

import io
import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from openpyxl import load_workbook
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureQuery,
)
from smb_requirement_agent.application.ports.generation_guidance import GenerationGuidance
from smb_requirement_agent.application.use_cases.approval_policy import artifact_fingerprint
from smb_requirement_agent.application.use_cases.export_breakdown import (
    _journey_step,
    _product_context,
)
from smb_requirement_agent.application.use_cases.impact_product_context import (
    MAX_JOURNEY_STEPS,
    journey_steps,
    product_contexts,
)
from smb_requirement_agent.application.use_cases.resolve_architecture_knowledge import (
    ResolveArchitectureKnowledge,
)
from smb_requirement_agent.domain.architecture.entities import (
    ArchitectureImpact,
    JourneyNeighbour,
    JourneyStep,
    OfferingDuty,
    ProductContext,
    SystemReference,
)
from smb_requirement_agent.domain.architecture.errors import InvalidArchitectureContentError
from smb_requirement_agent.domain.architecture.journeys import (
    Activity,
    FlowRule,
    FlowRuleKind,
    Journey,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    SystemDefinition,
)
from smb_requirement_agent.domain.architecture.products import (
    ComponentResponsibility,
    OfferingComponent,
    OrderType,
    ProductOffering,
)
from smb_requirement_agent.infrastructure.architecture.embeddings import FakeEmbeddings
from smb_requirement_agent.infrastructure.architecture.evidence_index import (
    InMemoryEvidenceIndex,
)
from smb_requirement_agent.infrastructure.architecture.knowledge_yaml import seed_knowledge
from smb_requirement_agent.infrastructure.architecture.reasoning import FakeArchitectureReasoner
from smb_requirement_agent.infrastructure.architecture.tokenizer import FakeWordTokenizer
from smb_requirement_agent.infrastructure.architecture.yaml_knowledge import (
    YamlArchitectureKnowledge,
    default_knowledge_path,
)
from smb_requirement_agent.infrastructure.exports.json_exporter import JsonBacklogExporter
from smb_requirement_agent.infrastructure.exports.xlsx_exporter import XlsxBacklogExporter
from smb_requirement_agent.infrastructure.llm.prompts.generation_guidance import render_guidance
from smb_requirement_agent.infrastructure.persistence.in_memory_architecture_knowledge import (
    InMemoryArchitectureKnowledgeRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_organisation import (
    InMemoryOrganisationRepository,
)
from smb_requirement_agent.infrastructure.persistence.shared_payloads import (
    architecture_from_payload,
    architecture_to_payload,
)
from tests.unit.test_backlog_export import _document
from tests.unit.test_feature_domain import make_feature

NOW = datetime(2026, 10, 1, tzinfo=UTC)

BPP = ProductOffering(
    "business-pro-plus",
    "Business Pro Plus",
    code="BUSINESS_PRO_PLUS",
    order_types=(
        OrderType("NEW_ACTIVATION", "New Activation"),
        OrderType("UPGRADE_DOWNGRADE", "Upgrade / Downgrade"),
    ),
    components=(
        OfferingComponent(
            "po-sdwan-new",
            "SDWAN & FortiPortal",
            code="PO_SDWAN_NEW",
            responsibilities=(
                ComponentResponsibility(
                    "bcrm", "CAPTURE", "Sells the SD-WAN option.", ("NEW_ACTIVATION",)
                ),
                ComponentResponsibility(
                    "cwom", "ORCHESTRATOR", "Orders its activation.", ("UPGRADE_DOWNGRADE",)
                ),
            ),
        ),
        OfferingComponent(
            "static-ip",
            "Static IP",
            responsibilities=(ComponentResponsibility("rtf", "VALIDATION", "Checks the IP."),),
        ),
    ),
)
OFFICE = ProductOffering(
    "office-connect",
    "Office Connect",
    order_types=(OrderType("NEW_ACTIVATION", "New Activation"),),
    components=(
        OfferingComponent(
            "fibre",
            "Fibre Access",
            responsibilities=(ComponentResponsibility("cwom", "ORCHESTRATOR", "Routes it."),),
        ),
    ),
)
ACTIVATION = Journey(
    "bpp-new-activation",
    "New Activation",
    product_id="business-pro-plus",
    order_type_code="NEW_ACTIVATION",
    activities=(
        Activity("10", "Select offer", performing_system_id="bcrm"),
        Activity("70", "Validate order", performing_system_id="rtf"),
        Activity(
            "75",
            "Correct order",
            track="CORRECTION",
            performing_system_id="b2b-web",
            supporting_system_ids=("bcrm",),
        ),
        Activity("80", "Route order", performing_system_id="cwom"),
    ),
    flow_rules=(
        FlowRule(FlowRuleKind.DECISION, "70", "80", "PASS"),
        FlowRule(FlowRuleKind.DECISION, "70", "75", "FAIL"),
        FlowRule(FlowRuleKind.LOOP, "75", "10", "Resubmit"),
    ),
)
OFFICE_JOURNEY = Journey(
    "office-new-activation",
    "New Activation",
    product_id="office-connect",
    order_type_code="NEW_ACTIVATION",
    activities=(Activity("10", "Order fibre", performing_system_id="bcrm"),),
)


def _release() -> ArchitectureKnowledge:
    systems = tuple(
        SystemDefinition(system_id, name)
        for system_id, name in (
            ("bcrm", "BCRM"),
            ("rtf", "RTF"),
            ("cwom", "CWOM"),
            ("b2b-web", "B2B Web"),
        )
    )
    return ArchitectureKnowledge(
        "v1", 1, systems, (), products=(OFFICE, BPP), journeys=(OFFICE_JOURNEY, ACTIVATION)
    )


# Product context --------------------------------------------------------------------------


def test_an_item_naming_an_offering_gets_its_systems_and_their_roles() -> None:
    (context,) = product_contexts(_release(), "Let Business Pro Plus customers add a branch")

    assert (context.product_id, context.product_name, context.order_type) == (
        "business-pro-plus",
        "Business Pro Plus",
        None,
    )
    # Its name and code are one offering, matched once.
    assert context.matched_terms == ("Business Pro Plus",)
    assert [
        (item.component_name, item.system_name, item.role) for item in context.responsibilities
    ] == [
        ("SDWAN & FortiPortal", "BCRM", "CAPTURE"),
        ("SDWAN & FortiPortal", "CWOM", "ORCHESTRATOR"),
        ("Static IP", "RTF", "VALIDATION"),
    ]


def test_a_named_component_and_order_type_narrow_the_responsibilities() -> None:
    (context,) = product_contexts(
        _release(), "BUSINESS_PRO_PLUS new activation: change the SDWAN & FortiPortal bundle"
    )

    assert context.order_type == "New Activation"
    # Words are named as the catalogue writes them.
    assert context.matched_terms == ("Business Pro Plus", "SDWAN & FortiPortal", "New Activation")
    # Only the component it named, and of its responsibilities only those for that order type.
    assert [(item.system_id, item.description) for item in context.responsibilities] == [
        ("bcrm", "Sells the SD-WAN option.")
    ]


def test_a_component_alone_names_its_offering_and_offerings_named_outrank_it() -> None:
    contexts = product_contexts(_release(), "Fibre access for Business Pro Plus sites")

    assert [item.product_id for item in contexts] == ["business-pro-plus", "office-connect"]
    office = contexts[1]
    assert office.matched_terms == ("Fibre Access",)
    assert [item.system_id for item in office.responsibilities] == ["cwom"]
    assert product_contexts(_release(), "Speed up billing") == ()
    assert product_contexts(_release(), "New Activation for everyone") == ()


# Journey steps ----------------------------------------------------------------------------


def test_a_mapped_system_shows_where_it_acts_and_who_hands_over() -> None:
    contexts = product_contexts(_release(), "Business Pro Plus")

    steps = journey_steps(_release(), {"bcrm", "rtf"}, contexts)

    # The offering the item names keeps the other offering's journey out.
    assert [(item.system_id, item.number, item.performs) for item in steps] == [
        ("bcrm", "10", True),
        ("rtf", "70", True),
        ("bcrm", "75", False),
    ]
    select, validate, correct = steps
    assert select.fulfils == ("Business Pro Plus", "New Activation")
    # The correction loop leads back into the first activity.
    assert select.before == (JourneyNeighbour("75", "Correct order", "b2b-web", "B2B Web"),)
    assert [item.number for item in validate.after] == ["80", "75"]
    assert [item.number for item in correct.before] == ["70"]


def test_every_journey_counts_when_no_offering_is_named_up_to_a_limit() -> None:
    steps = journey_steps(_release(), {"bcrm"})

    assert [(item.journey_id, item.number) for item in steps] == [
        ("office-new-activation", "10"),
        ("bpp-new-activation", "10"),
        ("bpp-new-activation", "75"),
    ]
    assert journey_steps(_release(), set()) == ()
    many = Journey(
        "many",
        "Many",
        activities=tuple(
            Activity(str(number), f"Step {number}", performing_system_id="bcrm")
            for number in range(1, 30)
        ),
    )
    crowded = replace(_release(), journeys=(many,))
    assert len(journey_steps(crowded, {"bcrm"})) == MAX_JOURNEY_STEPS


def test_mapping_adds_product_context_and_journey_steps_from_the_pinned_release() -> None:
    release = seed_knowledge()
    bcrm_offering = replace(
        BPP,
        components=(
            OfferingComponent(
                "po-sdwan-new",
                "SDWAN & FortiPortal",
                responsibilities=(ComponentResponsibility("bcrm", "CAPTURE", "Sells it."),),
            ),
        ),
    )
    journey = Journey(
        "bpp-new-activation",
        "New Activation",
        product_id="business-pro-plus",
        activities=(
            Activity("10", "Select offer", performing_system_id="bcrm"),
            Activity("20", "Create order", performing_system_id="rtf"),
        ),
    )
    pinned = replace(release, products=(bcrm_offering,), journeys=(journey,))
    resolver = ResolveArchitectureKnowledge(
        InMemoryArchitectureKnowledgeRepository(pinned),
        InMemoryEvidenceIndex(FakeEmbeddings(), FakeWordTokenizer()),
        FakeArchitectureReasoner(),
        YamlArchitectureKnowledge(default_knowledge_path()),
        InMemoryOrganisationRepository(FixedClock(NOW)),
    )

    match = resolver.match(
        ArchitectureQuery(text=("Business Pro Plus: the assisted sales journey",))
    )

    assert [item.id for item in match.systems] == ["bcrm"]
    (context,) = match.product_contexts
    assert [(item.system_name, item.role) for item in context.responsibilities] == [
        ("BCRM", "CAPTURE")
    ]
    (step,) = match.journey_steps
    assert (step.system_id, step.number, [item.system_name for item in step.after]) == (
        "bcrm",
        "10",
        ["RTF"],
    )


# Show-only --------------------------------------------------------------------------------


CONTEXT = ProductContext(
    "business-pro-plus",
    "Business Pro Plus",
    ("Business Pro Plus",),
    "New Activation",
    (OfferingDuty("static-ip", "Static IP", "rtf", "RTF", "VALIDATION", "Checks the IP."),),
)
STEP = JourneyStep(
    "crm",
    "bpp-new-activation",
    "New Activation",
    "10",
    "Select offer",
    True,
    ("Business Pro Plus", "New Activation"),
    (),
    (JourneyNeighbour("20", "Create order", "rtf", "RTF"), JourneyNeighbour("30", "Wait")),
)


def _impact() -> ArchitectureImpact:
    return ArchitectureImpact("v1", NOW, (SystemReference("crm", "CRM", True),))


def test_advice_persists_and_stays_out_of_fingerprints_and_prompts() -> None:
    bare = _impact()
    advised = replace(bare, product_contexts=(CONTEXT,), journey_steps=(STEP,))

    assert architecture_from_payload(architecture_to_payload(advised)) == advised
    legacy = architecture_to_payload(bare)
    assert isinstance(legacy, dict)
    assert "product_contexts" not in legacy and "journey_steps" not in legacy
    feature = make_feature()
    assert artifact_fingerprint(feature.with_architecture(advised)) == artifact_fingerprint(
        feature.with_architecture(bare)
    )
    match = ArchitectureKnowledgeMatch(
        "v1", bare.systems, (), product_contexts=(CONTEXT,), journey_steps=(STEP,)
    )
    plain = ArchitectureKnowledgeMatch("v1", bare.systems, ())
    assert render_guidance(GenerationGuidance(architecture=match)) == render_guidance(
        GenerationGuidance(architecture=plain)
    )
    with pytest.raises(InvalidArchitectureContentError, match="mapped systems"):
        replace(bare, journey_steps=(replace(STEP, system_id="other"),))
    with pytest.raises(InvalidArchitectureContentError, match="words that matched"):
        replace(CONTEXT, matched_terms=())


def test_exports_carry_product_context_and_journey_steps() -> None:
    document = _document("owner")
    feature = document.epic.features[0]
    assert feature.architecture is not None
    mapped = feature.architecture.systems[0].id
    architecture = replace(
        feature.architecture,
        product_contexts=(_product_context(CONTEXT),),
        journey_steps=(_journey_step(replace(STEP, system_id=mapped)),),
    )
    document = replace(
        document,
        epic=replace(document.epic, features=(replace(feature, architecture=architecture),)),
    )

    workbook = load_workbook(io.BytesIO(XlsxBacklogExporter().render(document)))
    header = [cell.value for cell in workbook["Product Context"][1]]
    (row,) = workbook["Product Context"].iter_rows(min_row=2, values_only=True)
    assert row[header.index("product_name")] == "Business Pro Plus"
    assert row[header.index("system_name")] == "RTF"
    assert row[header.index("order_type")] == "New Activation"
    header = [cell.value for cell in workbook["Journey Steps"][1]]
    (row,) = workbook["Journey Steps"].iter_rows(min_row=2, values_only=True)
    assert row[header.index("fulfils")] == "Business Pro Plus > New Activation"
    assert row[header.index("part")] == "performs"
    assert row[header.index("after")] == "20. Create order (RTF); 30. Wait"
    payload = json.loads(JsonBacklogExporter().render(document))
    exported = payload["epic"]["features"][0]["architecture"]
    assert exported["product_contexts"][0]["responsibilities"][0]["role"] == "VALIDATION"
    assert exported["journey_steps"][0]["after"][1] == {
        "number": "30",
        "name": "Wait",
        "system_id": None,
        "system_name": None,
    }
