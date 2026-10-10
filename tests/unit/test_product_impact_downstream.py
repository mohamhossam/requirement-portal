"""What a decided product impact changes after analysis (ADR-0115, ADR-0116).

Review flags what is undecided or uncertain, the review fingerprint follows only a
decision, generation follows the decided impact instead of a fresh match, mapped systems
carry their role and change type, and publication keeps the verdict it delivered.
Without a product impact every one of them is as it was.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.analysis.application.use_cases.product_impact import product_impact
from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.analysis.domain.product_impact import (
    ProductImpact,
    ProductImpactDecision,
    ProductImpactStatus,
    ProductVerdict,
)
from smb_requirement_agent.breakdown.application.ports.generation_guidance import (
    GenerationGuidance,
)
from smb_requirement_agent.breakdown.application.use_cases.architecture_mapping import (
    MapFeatureArchitecture,
)
from smb_requirement_agent.breakdown.application.use_cases.generation_checks import (
    GenerationChecks,
)
from smb_requirement_agent.breakdown.infrastructure.backlog_codecs import (
    architecture_from_payload,
    architecture_to_payload,
)
from smb_requirement_agent.breakdown.infrastructure.llm.prompts.generation_guidance import (
    render_guidance,
)
from smb_requirement_agent.governance.application.use_cases.publish_breakdown import (
    _decided_impact,
)
from smb_requirement_agent.governance.domain.review.entities import FlagCategory
from smb_requirement_agent.governance.domain.review.evidence import evidence_fingerprint
from smb_requirement_agent.governance.domain.review.policy import BreakdownReviewPolicy
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.config.options import (
    AdoPublisher,
    ConfigurationError,
    LLMProvider,
)
from smb_requirement_agent.infrastructure.config.settings import (
    AdoPublicationSettings,
    Settings,
)
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.references.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureQuery,
)
from smb_requirement_agent.references.domain.architecture.catalogue import SystemReference
from tests.characterisation import samples
from tests.knowledge_doubles import PublishedLibrary, service_for
from tests.unit.analysis.test_product_impact import ANSWER, StubAssessment
from tests.unit.workflow_helpers import approve_fake_breakdown

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


def _suggested() -> ProductImpact:
    return product_impact(ANSWER, NOW)


def _accepted() -> ProductImpact:
    return _suggested().decide(ProductImpactDecision.ACCEPTED, FAKE_ACTORS[0], NOW)


def _with(analysis: RequirementAnalysis, impact: ProductImpact | None) -> RequirementAnalysis:
    return replace(
        analysis,
        product_impact=impact,
        product_impact_status=ProductImpactStatus.ASSESSED if impact else None,
    )


# Review ----------------------------------------------------------------------------------


def _product_flags(impact: ProductImpact | None) -> dict[str, int]:
    evidence = samples.review_evidence()
    evidence = replace(evidence, analysis=_with(evidence.analysis, impact))
    review = BreakdownReviewPolicy().build(evidence, (samples.assessment(),), samples.T3)
    found: dict[str, int] = {}
    for flag in review.flags:
        if flag.category is FlagCategory.PRODUCT:
            title = flag.title
            found[title] = found.get(title, 0) + 1
    return found


def test_review_flags_an_undecided_verdict_and_a_weak_link() -> None:
    assert _product_flags(_suggested()) == {
        "Product verdict not decided": 1,
        "Weak capability link": 1,
    }


def test_review_flags_each_capability_gap_but_not_a_staffing_one() -> None:
    from smb_requirement_agent.analysis.domain.product_impact import ImpactGap

    impact = replace(
        _accepted(),
        gaps=(
            ImpactGap("capability", "cap:quota", "Usage quota", "No system realises it."),
            ImpactGap("staffing", "cap:static-ip", "Static IP", "No squad.", "bcrm"),
        ),
    )

    flags = _product_flags(impact)

    assert flags.get("A capability gap needs an architect") == 1
    assert "Product verdict not decided" not in flags


def test_an_unknown_verdict_stays_flagged_and_no_impact_flags_nothing() -> None:
    unknown = _suggested().decide(ProductImpactDecision.UNKNOWN, FAKE_ACTORS[0], NOW)

    assert _product_flags(unknown)["Product verdict not decided"] == 1
    assert _product_flags(None) == {}


def test_the_fingerprint_follows_only_a_decision() -> None:
    evidence = samples.review_evidence()
    baseline = evidence_fingerprint(evidence)

    def fingerprint(impact: ProductImpact | None) -> str:
        return evidence_fingerprint(replace(evidence, analysis=_with(evidence.analysis, impact)))

    overridden = _suggested().decide(
        ProductImpactDecision.OVERRIDDEN,
        FAKE_ACTORS[0],
        NOW,
        verdict=ProductVerdict.NEW_PLAN,
        rationale="Sold as a plan.",
    )
    # Existing approvals keep their fingerprints until someone decides (ADR-0115).
    assert fingerprint(None) == baseline
    assert fingerprint(_suggested()) == baseline
    assert fingerprint(_accepted()) != baseline
    assert fingerprint(overridden) not in {baseline, fingerprint(_accepted())}


# Generation ------------------------------------------------------------------------------


@dataclass
class _Knowledge:
    systems: tuple[SystemReference, ...] = (
        SystemReference("bcrm", "BCRM", True),
        SystemReference("cpp", "CPP", True),
    )
    queries: list[ArchitectureQuery] = field(default_factory=list)

    def match(self, query: ArchitectureQuery) -> ArchitectureKnowledgeMatch:
        self.queries.append(query)
        return ArchitectureKnowledgeMatch("rel-2026-10", self.systems, ())


def _checks(knowledge: _Knowledge) -> GenerationChecks:
    return GenerationChecks(
        knowledge,
        MapFeatureArchitecture(knowledge),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
    )


def test_generation_follows_a_decided_impact_instead_of_a_fresh_match() -> None:
    knowledge = _Knowledge()
    analysis = _with(samples.analysis(), _accepted())

    guidance = _checks(knowledge).guidance(samples.requirement(), analysis)

    assert guidance.product_impact == _accepted()
    assert guidance.architecture is None
    assert knowledge.queries == []


@pytest.mark.parametrize(
    "impact",
    [None, product_impact(ANSWER, NOW)],
    ids=["no impact", "undecided"],
)
def test_without_a_decided_verdict_generation_matches_as_before(
    impact: ProductImpact | None,
) -> None:
    knowledge = _Knowledge()

    guidance = _checks(knowledge).guidance(samples.requirement(), _with(samples.analysis(), impact))

    assert guidance.product_impact is None
    assert guidance.architecture is not None
    assert len(knowledge.queries) == 1


def test_the_prompt_carries_only_what_was_decided() -> None:
    without = render_guidance(GenerationGuidance())
    rendered = render_guidance(GenerationGuidance(product_impact=_accepted()))

    assert "DECIDED PRODUCT IMPACT" not in without
    head, block = rendered.split("DECIDED PRODUCT IMPACT (confirmed by a reviewer)\n")
    assert head.rstrip() == without.rstrip()
    decided = json.loads(block)
    assert decided["verdict"] == "change_existing_offering"
    assert decided["decision"] == "accepted"
    assert decided["offering"] == {"id": "offering:fiber", "name": "Business Fiber"}
    assert [item["id"] for item in decided["systems"]] == ["bcrm"]
    assert [item["id"] for item in decided["covered_capabilities"]] == ["cap:static-ip"]


def test_a_new_product_line_names_no_offering_in_the_prompt() -> None:
    line = _suggested().decide(
        ProductImpactDecision.OVERRIDDEN,
        FAKE_ACTORS[0],
        NOW,
        verdict=ProductVerdict.NEW_PRODUCT_LINE,
        rationale="A new line of business.",
    )

    decided = json.loads(
        render_guidance(GenerationGuidance(product_impact=line)).split("reviewer)\n")[1]
    )

    assert decided["offering"] is None


# Mapping ---------------------------------------------------------------------------------


def test_mapped_systems_carry_the_decided_role_and_change_type() -> None:
    knowledge = _Knowledge()
    mapper = MapFeatureArchitecture(knowledge)

    placed = mapper.execute(samples.requirement(), samples.feature(), NOW, decided=_accepted())
    plain = mapper.execute(samples.requirement(), samples.feature(), NOW)

    bcrm, cpp = placed.impact.systems
    assert (bcrm.role, bcrm.change_type) == ("primary", "modify")
    # A system the impact does not name keeps no role.
    assert (cpp.role, cpp.change_type) == (None, None)
    assert all(item.role is None for item in plain.impact.systems)
    restored = architecture_from_payload(architecture_to_payload(placed.impact))
    assert restored == placed.impact
    assert "role" not in json.dumps(architecture_to_payload(plain.impact))


# Publication -----------------------------------------------------------------------------


def test_publication_keeps_only_a_decided_verdict() -> None:
    analysis = samples.analysis()

    assert _decided_impact(None) == (None, None)
    assert _decided_impact(_with(analysis, _suggested())) == (None, None)
    assert _decided_impact(_with(analysis, _accepted())) == (
        "change_existing_offering",
        f"{samples.ANALYSIS_ID.value}@{analysis.version}",
    )


@pytest.fixture
def publishing() -> Iterator[tuple[TestClient, Container]]:
    container = build_container(
        Settings(
            llm_provider=LLMProvider.FAKE,
            ado_publication=AdoPublicationSettings(publisher=AdoPublisher.FAKE),
        ),
        knowledge_service=replace(service_for(PublishedLibrary()), assessment=StubAssessment()),
    )
    with TestClient(create_app(lambda: container)) as client:
        yield client, container
    container.close_resources()


def test_a_published_backlog_records_the_verdict_it_delivers(
    publishing: tuple[TestClient, Container],
) -> None:
    client, _ = publishing
    requirement_id, _, revision = approve_fake_breakdown(client)
    analysis = client.get(f"/requirements/{requirement_id}/analysis").json()
    path = f"/requirements/{requirement_id}/revisions/{revision}/publication"
    preview = client.get(path).json()

    published = client.post(path, json={"approval_fingerprint": preview["approval_fingerprint"]})

    assert published.status_code == 200, published.text
    status = client.get(f"/requirements/{requirement_id}/publication").json()
    assert status["product_verdict"] == "change_existing_offering"
    assert status["product_impact_version"] == (f"{analysis['analysis_id']}@{analysis['version']}")


# Settings --------------------------------------------------------------------------------


def test_the_verdict_gate_is_off_until_it_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRODUCT_VERDICT_VALIDATED", raising=False)
    assert Settings.from_env().product_verdict_validated is False
    monkeypatch.setenv("PRODUCT_VERDICT_VALIDATED", "true")
    assert Settings.from_env().product_verdict_validated is True
    monkeypatch.setenv("PRODUCT_VERDICT_VALIDATED", "yes")
    with pytest.raises(ConfigurationError):
        Settings.from_env()
