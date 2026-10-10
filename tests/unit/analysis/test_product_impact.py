"""A requirement's product impact, assessed in analysis and decided by its owner (ADR-0115)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.analysis.application.use_cases.product_impact import (
    AssessProductImpact,
    product_impact,
)
from smb_requirement_agent.analysis.domain.errors import InvalidProductImpactDecisionError
from smb_requirement_agent.analysis.domain.product_impact import (
    ProductImpact,
    ProductImpactDecision,
    ProductImpactStatus,
    ProductVerdict,
)
from smb_requirement_agent.application.errors import ServiceUnavailableError
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.references.application.ports.architecture_assessment import (
    ArchitectureAssessment,
    AssessedConcept,
    AssessedCoverage,
    AssessedFacet,
    AssessedOption,
    AssessedOwners,
    AssessedPathStep,
    AssessedProposal,
    AssessedQuestion,
    AssessedReference,
    AssessedSeat,
    AssessedSystem,
    AssessmentQuery,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.job_driver import run_job
from tests.knowledge_doubles import PublishedLibrary, service_for
from tests.unit.workflow_helpers import post_analysis, screen_current_knowledge

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)

QUESTION = AssessedQuestion(
    "offering",
    "Which offering does this change?",
    (AssessedOption("Business Fiber", "offering:fiber"), AssessedOption("Business ADSL")),
)

ANSWER = ArchitectureAssessment(
    knowledge_version="rel-2026-10",
    facets=(
        AssessedFacet(
            "need",
            "Static IP for SMB fibre",
            "static IP",
            concepts=(
                AssessedConcept("cap:static-ip", "Static IP", "Connectivity > Addressing"),
                AssessedConcept("cap:quota", "Usage quota", "Billing > Limits", weak=True),
            ),
        ),
    ),
    coverage=(
        AssessedCoverage(
            "cap:static-ip", "Static IP", "Connectivity > Addressing", ("c1",), ("bcrm",), True
        ),
        AssessedCoverage("cap:quota", "Usage quota", "Billing > Limits", (), (), False),
    ),
    offering_id="offering:fiber",
    verdict="change_existing_offering",
    rule_verdict="change_existing_offering",
    verdict_reason="Business Fiber already covers static IPs.",
    proposal=AssessedProposal("Add a static IP quota to Business Fiber.", "offering:fiber"),
    systems=(
        AssessedSystem(
            "bcrm",
            "BCRM",
            "primary",
            "modify",
            (
                (
                    AssessedPathStep("concept", "cap:static-ip", "Static IP"),
                    AssessedPathStep("offering", "offering:fiber", "Business Fiber"),
                    AssessedPathStep("system", "bcrm", "BCRM"),
                ),
            ),
        ),
    ),
    owners=(
        AssessedOwners(
            "cap:static-ip",
            "bcrm",
            squads=(AssessedReference("sales", "Sales squad"),),
            seats=(
                AssessedSeat("sales", "lead", "p1", "Mona Adel"),
                AssessedSeat("sales", "engineer"),
            ),
        ),
    ),
    model="fake-reader",
    prompt_version="assess-v1",
)


@dataclass
class StubAssessment:
    """The knowledge portal's assessment, answering whatever a test sets."""

    answer: ArchitectureAssessment | None = ANSWER
    connected: bool = True
    down: bool = False
    queries: list[AssessmentQuery] = field(default_factory=list)

    def is_connected(self) -> bool:
        return self.connected

    def assess(self, query: AssessmentQuery) -> ArchitectureAssessment | None:
        self.queries.append(query)
        if self.down:
            raise ServiceUnavailableError("The knowledge portal is down.")
        return self.answer


@dataclass(frozen=True)
class Portal:
    client: TestClient
    container: Container
    assessment: StubAssessment


@pytest.fixture
def portal() -> Iterator[Portal]:
    assessment = StubAssessment()
    container = build_container(
        Settings(llm_provider=LLMProvider.FAKE),
        knowledge_service=replace(service_for(PublishedLibrary()), assessment=assessment),
    )
    with TestClient(create_app(lambda: container)) as client:
        yield Portal(client, container, assessment)
    container.close_resources()


def _requirement(client: TestClient) -> str:
    response = client.post(
        "/requirements",
        json={"title": "Static IP quota", "description": "SMB fibre customers need a static IP."},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _analysis(client: TestClient, requirement_id: str) -> dict[str, Any]:
    response = client.get(f"/requirements/{requirement_id}/analysis")
    assert response.status_code == 200, response.text
    return dict(response.json())


def _answer_every_question(client: TestClient, requirement_id: str) -> dict[str, Any]:
    """Answer each open question; a catalogue one with its first option."""
    analysis = _analysis(client, requirement_id)
    answers = [
        {
            "question_id": question["id"],
            "answer": question["options"][0] if question["options"] else "Confirmed.",
            "expected_version": question["version"],
        }
        for question in analysis["questions"]
        if question["status"] in {"open", "in_progress"}
    ]
    resolved = run_job(client, requirement_id, "resolve_clarification_questions", answers=answers)
    assert resolved.succeeded, resolved.job
    analysis = _analysis(client, requirement_id)
    for proposal in analysis["business_intent"]["proposals"]:
        if proposal["status"] == "pending":
            decided = client.patch(
                f"/requirements/{requirement_id}/analysis/proposals/{proposal['id']}",
                json={"decision": "accepted", "expected_version": proposal["version"]},
            )
            assert decided.status_code == 200, decided.text
    return _analysis(client, requirement_id)


def _decide(client: TestClient, requirement_id: str, **body: object) -> dict[str, Any]:
    analysis = _analysis(client, requirement_id)
    response = client.put(
        f"/requirements/{requirement_id}/analysis/product-impact/decision",
        json={**body, "expected_version": analysis["version"]},
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


def _confirm(client: TestClient, requirement_id: str) -> int:
    screen_current_knowledge(client, requirement_id)
    analysis = _analysis(client, requirement_id)
    return client.post(
        f"/requirements/{requirement_id}/analysis/confirmation",
        json={"expected_version": analysis["version"]},
    ).status_code


# The application -------------------------------------------------------------------------


def test_analysis_asks_the_catalogue_and_its_question_blocks(portal: Portal) -> None:
    portal.assessment.answer = replace(ANSWER, verdict=None, questions=(QUESTION,))
    requirement_id = _requirement(portal.client)

    assert post_analysis(portal.client, requirement_id).succeeded

    analysis = _analysis(portal.client, requirement_id)
    assert analysis["product_impact_status"] == "assessed"
    impact = analysis["product_impact"]
    assert isinstance(impact, dict)
    assert impact["suggested_verdict"] is None
    assert impact["verdict_validated"] is False
    (catalogue,) = [item for item in analysis["questions"] if item["source"] == "catalogue"]
    assert catalogue["subject"] == "Which offering does this change?"
    assert catalogue["options"] == ["Business Fiber", "Business ADSL"]
    assert catalogue["is_blocker"] is True
    (query,) = portal.assessment.queries
    assert "Static IP quota" in query.text


def test_answering_the_catalogue_reassesses_and_confirmation_waits_for_a_decision(
    portal: Portal,
) -> None:
    portal.assessment.answer = replace(ANSWER, verdict=None, questions=(QUESTION,))
    requirement_id = _requirement(portal.client)
    assert post_analysis(portal.client, requirement_id).succeeded
    portal.assessment.answer = ANSWER

    analysis = _answer_every_question(portal.client, requirement_id)

    # The answer reached the knowledge portal, and its question is gone.
    assert "Business Fiber" in portal.assessment.queries[-1].text
    assert not any(
        item["source"] == "catalogue" and item["status"] == "open" for item in analysis["questions"]
    )
    impact = analysis["product_impact"]
    assert isinstance(impact, dict)
    assert impact["suggested_verdict"] == "change_existing_offering"
    assert impact["decision"] is None
    assert _confirm(portal.client, requirement_id) == 409

    decided = _decide(portal.client, requirement_id, decision="accepted")

    assert decided["product_impact"]["decision"] == "accepted"
    assert decided["product_impact"]["verdict"] == "change_existing_offering"
    assert _confirm(portal.client, requirement_id) == 200


def test_an_override_needs_another_verdict_and_a_reason(portal: Portal) -> None:
    requirement_id = _requirement(portal.client)
    assert post_analysis(portal.client, requirement_id).succeeded
    analysis = _analysis(portal.client, requirement_id)
    path = f"/requirements/{requirement_id}/analysis/product-impact/decision"

    same = portal.client.put(
        path,
        json={
            "decision": "overridden",
            "verdict": "change_existing_offering",
            "rationale": "Same.",
            "expected_version": analysis["version"],
        },
    )
    unexplained = portal.client.put(
        path,
        json={
            "decision": "overridden",
            "verdict": "new_plan",
            "expected_version": analysis["version"],
        },
    )
    stale = portal.client.put(
        path, json={"decision": "unknown", "expected_version": analysis["version"] + 1}
    )

    assert same.status_code == 422
    assert same.json()["code"] == "invalid_product_impact_decision"
    assert unexplained.status_code == 422
    assert stale.status_code == 409
    decided = _decide(
        portal.client,
        requirement_id,
        decision="overridden",
        verdict="new_plan",
        rationale="It is sold as a separate plan.",
    )
    assert decided["product_impact"]["verdict"] == "new_plan"


def test_no_knowledge_portal_assesses_nothing_and_blocks_nothing(portal: Portal) -> None:
    portal.assessment.connected = False
    requirement_id = _requirement(portal.client)
    assert post_analysis(portal.client, requirement_id).succeeded

    analysis = _analysis(portal.client, requirement_id)

    assert analysis["product_impact_status"] == "not_connected"
    assert analysis["product_impact"] is None
    assert portal.assessment.queries == []
    decided = portal.client.put(
        f"/requirements/{requirement_id}/analysis/product-impact/decision",
        json={"decision": "unknown", "expected_version": analysis["version"]},
    )
    assert decided.status_code == 404
    assert decided.json()["code"] == "product_impact_not_found"
    _answer_every_question(portal.client, requirement_id)
    assert _confirm(portal.client, requirement_id) == 200


def test_an_unreachable_portal_keeps_the_earlier_impact_and_its_decision(portal: Portal) -> None:
    requirement_id = _requirement(portal.client)
    assert post_analysis(portal.client, requirement_id).succeeded
    _decide(portal.client, requirement_id, decision="accepted")
    portal.assessment.down = True

    analysis = _answer_every_question(portal.client, requirement_id)

    assert analysis["product_impact_status"] == "unavailable"
    assert analysis["product_impact"]["decision"] == "accepted"
    assert _confirm(portal.client, requirement_id) == 200


def test_a_decision_survives_a_round_whose_suggestion_is_unchanged(portal: Portal) -> None:
    requirement_id = _requirement(portal.client)
    assert post_analysis(portal.client, requirement_id).succeeded
    _decide(portal.client, requirement_id, decision="accepted")

    kept = _answer_every_question(portal.client, requirement_id)
    assert kept["product_impact"]["decision"] == "accepted"

    portal.assessment.answer = replace(ANSWER, verdict="new_plan")
    run = post_analysis(portal.client, requirement_id, force=True)
    assert run.succeeded, run.job
    changed = _analysis(portal.client, requirement_id)
    assert changed["product_impact"]["suggested_verdict"] == "new_plan"
    assert changed["product_impact"]["decision"] is None


def test_the_owner_decides_and_a_confirmed_analysis_is_locked(portal: Portal) -> None:
    requirement_id = _requirement(portal.client)
    assert post_analysis(portal.client, requirement_id).succeeded
    _answer_every_question(portal.client, requirement_id)
    _decide(portal.client, requirement_id, decision="unknown")
    assert _confirm(portal.client, requirement_id) == 200
    analysis = _analysis(portal.client, requirement_id)

    locked = portal.client.put(
        f"/requirements/{requirement_id}/analysis/product-impact/decision",
        json={"decision": "accepted", "expected_version": analysis["version"]},
    )

    assert locked.status_code == 409
    assert locked.json()["code"] == "product_impact_decision_locked"


# Mapping the knowledge portal's answer ---------------------------------------------------


def test_the_answer_maps_into_requirement_terms() -> None:
    impact = product_impact(ANSWER, NOW)

    assert impact.suggested_verdict is ProductVerdict.CHANGE_EXISTING_OFFERING
    assert impact.offering_name == "Business Fiber"
    assert [need.concept_id for need in impact.covered_needs] == ["cap:static-ip"]
    assert [need.concept_id for need in impact.weak_needs] == ["cap:quota"]
    (owner,) = impact.owners
    assert owner.squads == ("Sales squad",)
    assert owner.people == ("Mona Adel",)
    assert owner.open_seats == 1
    (system,) = impact.systems
    assert (system.role, system.change_type) == ("primary", "modify")


def test_a_role_the_portal_adds_later_is_kept_as_written() -> None:
    (system,) = ANSWER.systems
    impact = product_impact(replace(ANSWER, systems=(replace(system, role="owner"),)), NOW)

    assert impact.systems[0].role == "owner"


@pytest.mark.parametrize(
    ("assessment", "status"),
    [
        (StubAssessment(connected=False), ProductImpactStatus.NOT_CONNECTED),
        (StubAssessment(down=True), ProductImpactStatus.UNAVAILABLE),
        (StubAssessment(answer=None), ProductImpactStatus.NOT_CONNECTED),
        (
            StubAssessment(answer=replace(ANSWER, knowledge_version=" ")),
            ProductImpactStatus.UNAVAILABLE,
        ),
    ],
)
def test_an_assessment_that_cannot_be_used_says_why(
    assessment: StubAssessment, status: ProductImpactStatus
) -> None:
    candidate = AssessProductImpact(assessment, FixedClock(NOW)).augment(
        Requirement(
            id=RequirementId("req-impact"),
            title=RequirementTitle("Static IP quota"),
            description=RequirementDescription("SMB fibre customers need a static IP."),
            status=RequirementStatus.DRAFT,
        ),
        {
            "known_facts": [],
            "constraints": [],
            "business_rules": [],
        },  # type: ignore[typeddict-item]
        (),
    )

    assert candidate.get("product_impact_status") is status
    assert candidate.get("product_impact") is None


# The domain ------------------------------------------------------------------------------


def _impact(**changes: object) -> ProductImpact:
    return replace(product_impact(ANSWER, NOW), **changes)  # type: ignore[arg-type]


def test_accepting_takes_the_suggestion_and_overriding_needs_a_reason() -> None:
    actor = FAKE_ACTORS[0]
    accepted = _impact().decide(ProductImpactDecision.ACCEPTED, actor, NOW)
    assert accepted.verdict is ProductVerdict.CHANGE_EXISTING_OFFERING
    assert accepted.decided_offering_id == "offering:fiber"

    with pytest.raises(InvalidProductImpactDecisionError):
        _impact().decide(
            ProductImpactDecision.OVERRIDDEN, actor, NOW, verdict=ProductVerdict.NEW_PRODUCT_LINE
        )
    with pytest.raises(InvalidProductImpactDecisionError):
        _impact().decide(
            ProductImpactDecision.OVERRIDDEN,
            actor,
            NOW,
            verdict=ProductVerdict.CHANGE_EXISTING_OFFERING,
            rationale="Same.",
        )
    with pytest.raises(InvalidProductImpactDecisionError):
        _impact(suggested_verdict=None).decide(ProductImpactDecision.ACCEPTED, actor, NOW)

    line = _impact().decide(
        ProductImpactDecision.OVERRIDDEN,
        actor,
        NOW,
        verdict=ProductVerdict.NEW_PRODUCT_LINE,
        rationale="A new line of business.",
    )
    # A new product line changes no existing offering.
    assert line.decided_offering_id is None
    unknown = _impact().decide(ProductImpactDecision.UNKNOWN, actor, NOW)
    assert unknown.verdict is None
    assert unknown.is_decided


def test_a_decision_carries_only_while_its_suggestion_stands() -> None:
    decided = _impact().decide(ProductImpactDecision.ACCEPTED, FAKE_ACTORS[0], NOW)
    later = NOW + timedelta(hours=1)

    assert _impact(assessed_at=later).carried_from(decided).decision is (
        ProductImpactDecision.ACCEPTED
    )
    assert (
        _impact(assessed_at=later, suggested_verdict=ProductVerdict.NEW_PLAN)
        .carried_from(decided)
        .decision
        is None
    )
    assert _impact(offering_id="offering:adsl").carried_from(decided).decision is None
    assert _impact().carried_from(None).decision is None
