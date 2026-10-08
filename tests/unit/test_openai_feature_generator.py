"""Tests for the OpenAI Feature generator adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.analysis.domain.value_objects import (
    Assumption,
    BusinessRule,
    Constraint,
    KnownFact,
    OpenQuestion,
)
from smb_requirement_agent.application.errors import FeatureGenerationError
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.breakdown.domain.epic.value_objects import (
    BusinessCase,
    BusinessOutcome,
    EpicId,
    EpicName,
    EpicStatus,
)
from smb_requirement_agent.breakdown.infrastructure.llm.prompts.feature_prompt import PROMPT_VERSION
from smb_requirement_agent.infrastructure.llm.openai_adapters import (
    OpenAIFeatureGenerator,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

GENERATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


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
        constraints=(Constraint("B2B portal only"),),
        business_rules=(BusinessRule("SMB customers only"),),
        assumptions=(Assumption("Billing already supports bundles"),),
        open_questions=(OpenQuestion(question="Which channels?", rationale="Scope"),),
        ambiguities=(),
        potential_dependencies=(),
    )


@pytest.fixture
def epic() -> Epic:
    return Epic(
        id=EpicId("epic-1"),
        requirement_id=RequirementId("req-1"),
        name=EpicName("SMB Bundle Offer"),
        outcome=BusinessOutcome("Bundles orderable in channel"),
        business_case=BusinessCase("Grows attach rate"),
        status=EpicStatus.APPROVED,
        provenance=Provenance(generated_at=GENERATED_AT, model="gpt-4o", prompt_version="epic-v1"),
    )


def _item(
    name: str = "Ordering",
    outcome: str = "Order in channel",
    rationale: str = "Journey stage",
    drop: str = "mvp",
    pattern: str = "journey_stage",
) -> MagicMock:
    item = MagicMock()
    item.name = name
    item.outcome = outcome
    item.delivery_drop = drop
    item.splitting_pattern = pattern
    item.splitting_rationale = rationale
    return item


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


def _parsed(*items: MagicMock) -> MagicMock:
    parsed = MagicMock()
    parsed.features = list(items)
    return parsed


@patch("smb_requirement_agent.infrastructure.llm.openai_adapters.OpenAI")
def test_success_maps_every_item(
    mock_openai: MagicMock,
    requirement: Requirement,
    analysis: RequirementAnalysis,
    epic: Epic,
) -> None:
    mock_openai.return_value = _client_returning(_parsed(_item(), _item(name="Fulfilment")))

    candidates = OpenAIFeatureGenerator(
        mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
    ).generate(requirement, analysis, epic)

    assert [c["name"] for c in candidates] == ["Ordering", "Fulfilment"]
    assert all(c["prompt_version"] == PROMPT_VERSION for c in candidates)
    assert all(c["model"] == "gpt-4o" for c in candidates)


@patch("smb_requirement_agent.infrastructure.llm.openai_adapters.OpenAI")
def test_items_with_blank_fields_are_dropped(
    mock_openai: MagicMock,
    requirement: Requirement,
    analysis: RequirementAnalysis,
    epic: Epic,
) -> None:
    """A schema-valid item can still be unusable; it must not reach the domain."""
    mock_openai.return_value = _client_returning(
        _parsed(_item(name="  "), _item(name="Good"), _item(rationale="   "))
    )

    candidates = OpenAIFeatureGenerator(
        mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
    ).generate(requirement, analysis, epic)

    assert [c["name"] for c in candidates] == ["Good"]


@patch("smb_requirement_agent.infrastructure.llm.openai_adapters.OpenAI")
def test_zero_features_is_a_generation_error(
    mock_openai: MagicMock,
    requirement: Requirement,
    analysis: RequirementAnalysis,
    epic: Epic,
) -> None:
    """An Epic that decomposes into nothing is a failure, not an empty answer."""
    mock_openai.return_value = _client_returning(_parsed())

    with pytest.raises(FeatureGenerationError, match="no usable Features"):
        OpenAIFeatureGenerator(
            mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
        ).generate(requirement, analysis, epic)


@patch("smb_requirement_agent.infrastructure.llm.openai_adapters.OpenAI")
def test_all_items_blank_is_a_generation_error(
    mock_openai: MagicMock,
    requirement: Requirement,
    analysis: RequirementAnalysis,
    epic: Epic,
) -> None:
    mock_openai.return_value = _client_returning(_parsed(_item(name="  "), _item(outcome=" ")))

    with pytest.raises(FeatureGenerationError):
        OpenAIFeatureGenerator(
            mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
        ).generate(requirement, analysis, epic)


@patch("smb_requirement_agent.infrastructure.llm.openai_adapters.OpenAI")
def test_empty_choices_is_a_generation_error(
    mock_openai: MagicMock,
    requirement: Requirement,
    analysis: RequirementAnalysis,
    epic: Epic,
) -> None:
    mock_openai.return_value = _client_returning(parsed=None, choices=[])

    with pytest.raises(FeatureGenerationError):
        OpenAIFeatureGenerator(
            mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
        ).generate(requirement, analysis, epic)


@patch("smb_requirement_agent.infrastructure.llm.openai_adapters.OpenAI")
def test_provider_error_is_mapped(
    mock_openai: MagicMock,
    requirement: Requirement,
    analysis: RequirementAnalysis,
    epic: Epic,
) -> None:
    from openai import OpenAIError

    client = MagicMock()
    client.chat.completions.parse.side_effect = OpenAIError("boom")
    mock_openai.return_value = client

    with pytest.raises(FeatureGenerationError, match="Feature generation failed"):
        OpenAIFeatureGenerator(
            mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
        ).generate(requirement, analysis, epic)


@patch("smb_requirement_agent.infrastructure.llm.openai_adapters.OpenAI")
def test_prompt_carries_the_epic_and_labels_unconfirmed_analysis(
    mock_openai: MagicMock,
    requirement: Requirement,
    analysis: RequirementAnalysis,
    epic: Epic,
) -> None:
    client = _client_returning(_parsed(_item()))
    mock_openai.return_value = client

    OpenAIFeatureGenerator(mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0).generate(
        requirement, analysis, epic
    )

    prompt = client.chat.completions.parse.call_args.kwargs["messages"][1]["content"]
    assert "SMB Bundle Offer" in prompt
    assert prompt.index("NOT CONFIRMED") < prompt.index("Billing already supports bundles")
