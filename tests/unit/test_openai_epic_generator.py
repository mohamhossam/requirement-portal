"""Tests for the OpenAI Epic generator adapter."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.analysis.domain.value_objects import (
    Ambiguity,
    Assumption,
    BusinessRule,
    Constraint,
    IntentProposal,
    IntentProposalId,
    IntentProposalKind,
    IntentProposalStatus,
    KnownFact,
    OpenQuestion,
    PotentialDependency,
)
from smb_requirement_agent.breakdown.application.errors import EpicGenerationError
from smb_requirement_agent.breakdown.infrastructure.llm.openai_adapters import OpenAIEpicGenerator
from smb_requirement_agent.breakdown.infrastructure.llm.prompts.epic_prompt import PROMPT_VERSION
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@pytest.fixture
def requirement() -> Requirement:
    return Requirement(
        id=RequirementId("req-1"),
        title=RequirementTitle("Bundle ordering"),
        description=RequirementDescription("Order bundles in channel"),
        status=RequirementStatus.DRAFT,
    )


@pytest.fixture
def analysis() -> RequirementAnalysis:
    return RequirementAnalysis(
        requirement_id=RequirementId("req-1"),
        known_facts=(KnownFact("Bundles exist"),),
        constraints=(Constraint("Must work in B2B portal"),),
        business_rules=(BusinessRule("Only SMB customers"),),
        assumptions=(Assumption("Billing already supports bundles"),),
        open_questions=(OpenQuestion(question="Which channels?", rationale="Scope"),),
        ambiguities=(Ambiguity(statement="'in channel'", reason="Undefined"),),
        potential_dependencies=(PotentialDependency("Provisioning"),),
    )


def _client_returning(
    parsed: MagicMock | None, choices: list[MagicMock] | None = None
) -> MagicMock:
    client = MagicMock()
    if choices is None:
        choice = MagicMock()
        choice.message.parsed = parsed
        choices = [choice]
    response = MagicMock()
    response.choices = choices
    client.chat.completions.parse.return_value = response
    return client


def _parsed(
    name: str = "SMB Bundle Offer", outcome: str = "Bundles orderable", case: str = "Growth"
) -> MagicMock:
    parsed = MagicMock()
    parsed.name = name
    parsed.outcome = outcome
    parsed.business_case = case
    return parsed


@patch("smb_requirement_agent.breakdown.infrastructure.llm.openai_adapters.OpenAI")
def test_success_maps_to_a_candidate_with_provenance(
    mock_openai: MagicMock, requirement: Requirement, analysis: RequirementAnalysis
) -> None:
    mock_openai.return_value = _client_returning(_parsed())

    candidate = OpenAIEpicGenerator(
        mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
    ).generate(requirement, analysis)

    assert candidate["name"] == "SMB Bundle Offer"
    assert candidate["model"] == "gpt-4o"
    assert candidate["prompt_version"] == PROMPT_VERSION


@patch("smb_requirement_agent.breakdown.infrastructure.llm.openai_adapters.OpenAI")
def test_surrounding_whitespace_is_stripped(
    mock_openai: MagicMock, requirement: Requirement, analysis: RequirementAnalysis
) -> None:
    mock_openai.return_value = _client_returning(_parsed(name="  Padded  "))

    candidate = OpenAIEpicGenerator(
        mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
    ).generate(requirement, analysis)

    assert candidate["name"] == "Padded"


@pytest.mark.parametrize("blank_field", ["name", "outcome", "business_case"])
@patch("smb_requirement_agent.breakdown.infrastructure.llm.openai_adapters.OpenAI")
def test_a_blank_field_is_a_generation_error_not_a_domain_error(
    mock_openai: MagicMock,
    blank_field: str,
    requirement: Requirement,
    analysis: RequirementAnalysis,
) -> None:
    """A schema-valid response with a blank field must not reach the domain."""
    parsed = _parsed()
    setattr(parsed, blank_field, "   ")
    mock_openai.return_value = _client_returning(parsed)

    with pytest.raises(EpicGenerationError, match=blank_field):
        OpenAIEpicGenerator(
            mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
        ).generate(requirement, analysis)


@patch("smb_requirement_agent.breakdown.infrastructure.llm.openai_adapters.OpenAI")
def test_empty_choices_is_a_generation_error(
    mock_openai: MagicMock, requirement: Requirement, analysis: RequirementAnalysis
) -> None:
    mock_openai.return_value = _client_returning(parsed=None, choices=[])

    with pytest.raises(EpicGenerationError):
        OpenAIEpicGenerator(
            mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
        ).generate(requirement, analysis)


@patch("smb_requirement_agent.breakdown.infrastructure.llm.openai_adapters.OpenAI")
def test_unparseable_response_is_a_generation_error(
    mock_openai: MagicMock, requirement: Requirement, analysis: RequirementAnalysis
) -> None:
    mock_openai.return_value = _client_returning(parsed=None)

    with pytest.raises(EpicGenerationError):
        OpenAIEpicGenerator(
            mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
        ).generate(requirement, analysis)


@patch("smb_requirement_agent.breakdown.infrastructure.llm.openai_adapters.OpenAI")
def test_provider_error_is_mapped(
    mock_openai: MagicMock, requirement: Requirement, analysis: RequirementAnalysis
) -> None:
    from openai import OpenAIError

    client = MagicMock()
    client.chat.completions.parse.side_effect = OpenAIError("boom")
    mock_openai.return_value = client

    with pytest.raises(EpicGenerationError, match="Epic generation failed"):
        OpenAIEpicGenerator(
            mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
        ).generate(requirement, analysis)


@patch("smb_requirement_agent.breakdown.infrastructure.llm.openai_adapters.OpenAI")
def test_unconfirmed_analysis_is_labelled_in_the_prompt(
    mock_openai: MagicMock, requirement: Requirement, analysis: RequirementAnalysis
) -> None:
    """Assumptions must not be presented to the model as source truth."""
    client = _client_returning(_parsed())
    mock_openai.return_value = client

    OpenAIEpicGenerator(mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0).generate(
        requirement, analysis
    )

    user_prompt = client.chat.completions.parse.call_args.kwargs["messages"][1]["content"]
    assumption_pos = user_prompt.index("Billing already supports bundles")
    warning_pos = user_prompt.index("NOT CONFIRMED")
    assert warning_pos < assumption_pos


@patch("smb_requirement_agent.breakdown.infrastructure.llm.openai_adapters.OpenAI")
def test_prompt_includes_only_owner_confirmed_intent_proposals(
    mock_openai: MagicMock, requirement: Requirement, analysis: RequirementAnalysis
) -> None:
    client = _client_returning(_parsed())
    mock_openai.return_value = client
    actor = FAKE_ACTORS[0].snapshot()
    at = datetime(2026, 9, 4, tzinfo=UTC)
    outcome = IntentProposal(
        IntentProposalId("outcome-1"),
        IntentProposalKind.DESIRED_OUTCOME,
        "Customers complete ordering online.",
        "Outcome candidate.",
    ).decide(IntentProposalStatus.ACCEPTED, actor, at, 1)
    accepted_rule = IntentProposal(
        IntentProposalId("rule-1"),
        IntentProposalKind.BUSINESS_RULE,
        "The owner validates the order.",
        "Rule candidate.",
    ).decide(IntentProposalStatus.ACCEPTED, actor, at, 1)
    rejected_constraint = IntentProposal(
        IntentProposalId("constraint-1"),
        IntentProposalKind.CONSTRAINT,
        "Use the unverified legacy platform.",
        "Constraint candidate.",
    ).decide(IntentProposalStatus.REJECTED, actor, at, 1)

    OpenAIEpicGenerator(mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0).generate(
        requirement,
        replace(
            analysis,
            intent_proposals=(outcome, accepted_rule, rejected_constraint),
        ),
    )

    prompt = client.chat.completions.parse.call_args.kwargs["messages"][1]["content"]
    assert "Confirmed desired outcome: Customers complete ordering online." in prompt
    assert "The owner validates the order." in prompt
    assert "Use the unverified legacy platform." not in prompt
