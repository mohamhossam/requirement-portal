"""Non-functional requirements and business use cases as settled analysis categories (ADR-0120)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.analysis.application.errors import RequirementAnalysisGenerationError
from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    BusinessUseCaseCandidate,
    NonFunctionalRequirementCandidate,
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.analysis.application.use_cases.analysis_mapping import (
    analysis_evidence_key,
)
from smb_requirement_agent.analysis.application.use_cases.evidence_analysis import (
    ConsolidateEvidenceAnalysis,
    ValidateAnalysisCitations,
)
from smb_requirement_agent.analysis.domain.errors import InvalidAnalysisContentError
from smb_requirement_agent.analysis.domain.value_objects import (
    BusinessUseCase,
    NonFunctionalKind,
    NonFunctionalRequirement,
)
from smb_requirement_agent.analysis.infrastructure.analysis_payloads import (
    analysis_from_payload,
    analysis_to_payload,
)
from smb_requirement_agent.analysis.infrastructure.llm.response_sanitizer import (
    clean_typed_statements,
    clean_use_cases,
)
from smb_requirement_agent.governance.domain.review.evidence import (
    ReviewEvidence,
    evidence_fingerprint,
)
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.unit.workflow_helpers import post_analysis

NOW = datetime(2026, 9, 4, 8, 30, tzinfo=UTC)


def _use_case(**overrides: object) -> BusinessUseCaseCandidate:
    base = BusinessUseCaseCandidate(
        name="Customer orders a plan",
        actor="SMB customer",
        trigger=None,
        goal="The plan is active.",
        main_steps=["Choose a plan", "Place the order"],
        alternate_paths=[],
        business_rules=[],
    )
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def _candidate(**extra: object) -> RequirementAnalysisCandidate:
    candidate = RequirementAnalysisCandidate(
        known_facts=["A fact."],
        constraints=[],
        business_rules=[],
        assumptions=[],
        open_questions=[],
        ambiguities=[],
        potential_dependencies=[],
        intent_proposals=[],
        model="m",
        prompt_version="p",
    )
    candidate.update(extra)  # type: ignore[typeddict-item]
    return candidate


# --- domain -----------------------------------------------------------------------------------


def test_use_case_needs_name_actor_goal_and_a_step_and_strips_its_fields() -> None:
    use_case = BusinessUseCase(
        name="  Customer orders a plan ",
        actor=" SMB customer",
        goal="The plan is active. ",
        main_steps=(" Choose a plan ", "", "Place the order"),
        trigger="  ",
        alternate_paths=("", " Eligibility fails "),
    )

    assert use_case.name == "Customer orders a plan"
    assert use_case.main_steps == ("Choose a plan", "Place the order")
    assert use_case.trigger is None
    assert use_case.alternate_paths == ("Eligibility fails",)
    with pytest.raises(InvalidAnalysisContentError):
        BusinessUseCase(name="x", actor="y", goal="z", main_steps=(" ",))
    with pytest.raises(InvalidAnalysisContentError):
        BusinessUseCase(name="x", actor=" ", goal="z", main_steps=("a",))
    with pytest.raises(InvalidAnalysisContentError):
        NonFunctionalRequirement(" ", NonFunctionalKind.PERFORMANCE)


# --- sanitiser --------------------------------------------------------------------------------


def test_sanitiser_drops_blank_items_defaults_unknown_kinds_and_dedupes() -> None:
    kinds = frozenset(kind.value for kind in NonFunctionalKind)

    typed = clean_typed_statements(
        [(" Fast ", "performance"), ("", "security"), ("fast", "security"), ("Safe", "nonsense")],
        kinds,
        "other",
    )
    use_cases = clean_use_cases(
        [
            {"name": " A ", "actor": "x", "goal": "y", "main_steps": [" one ", ""]},
            {"name": "a", "actor": "x", "goal": "y", "main_steps": ["dup"]},
            {"name": "No actor", "actor": " ", "goal": "y", "main_steps": ["one"]},
            {"name": "No steps", "actor": "x", "goal": "y", "main_steps": [" "]},
            {"name": "B", "actor": "x", "goal": "y", "main_steps": ["one"], "trigger": " when "},
        ]
    )

    assert typed == [("Fast", "performance"), ("Safe", "other")]
    assert [item["name"] for item in use_cases] == ["A", "B"]
    assert use_cases[0]["main_steps"] == ["one"]
    assert use_cases[0]["trigger"] is None
    assert use_cases[1]["trigger"] == "when"


# --- packets ----------------------------------------------------------------------------------


def test_merge_keeps_use_cases_by_name_and_typed_statements_by_statement() -> None:
    first = _candidate(
        non_functional_requirements=[
            NonFunctionalRequirementCandidate(statement="Fast", kind="performance")
        ],
        business_use_cases=[_use_case()],
        evidence_references={
            analysis_evidence_key("known_fact", "A fact."): [],
            analysis_evidence_key("business_use_case", "Customer orders a plan"): [],
        },
    )
    second = _candidate(
        non_functional_requirements=[
            NonFunctionalRequirementCandidate(statement="FAST", kind="security")
        ],
        business_use_cases=[_use_case(name="customer orders a plan"), _use_case(name="Renew")],
    )

    merged = ConsolidateEvidenceAnalysis._merge([first, second], ())

    assert [item["statement"] for item in merged["non_functional_requirements"]] == ["Fast"]
    assert merged["non_functional_requirements"][0]["kind"] == "performance"
    assert [item["name"] for item in merged["business_use_cases"]] == [
        "Customer orders a plan",
        "Renew",
    ]


def test_citation_validator_expects_a_citation_for_each_use_case_and_requirement() -> None:
    candidate = _candidate(
        non_functional_requirements=[
            NonFunctionalRequirementCandidate(statement="Fast", kind="performance")
        ],
        business_use_cases=[_use_case()],
        requirement_references=[analysis_evidence_key("known_fact", "A fact.")],
    )

    with pytest.raises(RequirementAnalysisGenerationError, match="did not cite every"):
        ValidateAnalysisCitations().execute(candidate, ())

    candidate["requirement_references"] = [
        analysis_evidence_key("known_fact", "A fact."),
        analysis_evidence_key("non_functional_requirement", "Fast"),
        analysis_evidence_key("business_use_case", "Customer orders a plan"),
    ]
    ValidateAnalysisCitations().execute(candidate, ())


# --- fake analyzer through the API and the codec ------------------------------------------


def test_fake_analysis_carries_both_categories_through_api_and_codec(
    client: TestClient, container: Container
) -> None:
    requirement_id = client.post(
        "/requirements", json={"title": "Settled", "description": "A need."}
    ).json()["id"]
    assert post_analysis(client, requirement_id).succeeded

    body = client.get(f"/requirements/{requirement_id}/analysis").json()

    assert body["non_functional_requirements"] == [
        {
            "statement": "Order confirmation is shown within 5 seconds.",
            "kind": "performance",
            "evidence_references": [],
        }
    ]
    use_case = body["business_use_cases"][0]
    assert use_case["name"] == "SMB customer orders a plan"
    assert use_case["main_steps"] == ["Choose a plan", "Confirm eligibility", "Place the order"]
    assert use_case["business_rules"] == ["This is a business rule."]

    analysis = container.analysis_repository.get_by_requirement_id(RequirementId(requirement_id))
    assert analysis is not None
    payload = analysis_to_payload(analysis)
    rows = payload["non_functional_requirements"]
    assert isinstance(rows, list)
    first = rows[0]
    assert isinstance(first, dict) and first["kind"] == "performance"
    assert analysis_from_payload(payload) == analysis
    # A payload from before the categories existed still reads, with empty tuples.
    legacy = {
        key: value
        for key, value in payload.items()
        if key not in ("non_functional_requirements", "business_use_cases")
    }
    older = analysis_from_payload(legacy)
    assert older.non_functional_requirements == ()
    assert older.business_use_cases == ()
    assert "non_functional_requirements" not in analysis_to_payload(older)


def test_fingerprint_changes_only_when_the_categories_are_present(
    client: TestClient, container: Container
) -> None:
    requirement_id = client.post(
        "/requirements", json={"title": "Settled", "description": "A need."}
    ).json()["id"]
    assert post_analysis(client, requirement_id).succeeded
    requirement = container.requirement_repository.get(RequirementId(requirement_id))
    analysis = container.analysis_repository.get_by_requirement_id(RequirementId(requirement_id))
    assert requirement is not None and analysis is not None
    bare = replace(analysis, non_functional_requirements=(), business_use_cases=())

    def fingerprint(value: object) -> str:
        return evidence_fingerprint(
            ReviewEvidence(
                requirement=requirement,
                analysis=value,  # type: ignore[arg-type]
                epic=None,
                features=(),
                stories=(),
                questions=(),
                stale_reference_proposal_ids=(),
            )
        )

    assert fingerprint(bare) != fingerprint(analysis)
    assert fingerprint(bare) == fingerprint(
        replace(bare, non_functional_requirements=(), business_use_cases=())
    )
