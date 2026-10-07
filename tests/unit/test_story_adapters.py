"""Story adapter boundary validation tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from openai import OpenAIError
from pydantic import ValidationError
from smb_kernel.llm.local_structured_output import (
    LocalLLMError,
    LocalStructuredOutputClient,
)

from smb_requirement_agent.application.errors import StoryGenerationError
from smb_requirement_agent.application.ports.generation_guidance import GenerationGuidance
from smb_requirement_agent.domain.story.quality import InvestCriterion, StoryQualityEvidence
from smb_requirement_agent.infrastructure.llm.candidate_mappers import to_story_candidates
from smb_requirement_agent.infrastructure.llm.local_story_generator import LocalStoryGenerator
from smb_requirement_agent.infrastructure.llm.openai_adapters import OpenAIStoryGenerator
from smb_requirement_agent.infrastructure.llm.prompts.story_prompt import PROMPT_VERSION
from smb_requirement_agent.infrastructure.llm.prompts.story_quality_prompt import (
    build_story_quality_prompt,
)
from smb_requirement_agent.infrastructure.llm.schemas.story_schema import (
    AcceptanceCriterionSchema,
    StoryItemSchema,
    StorySetSchema,
)


def _criterion(
    given: str = "the customer is eligible",
    when: str = "the customer orders",
    then: str = "the order is accepted",
) -> AcceptanceCriterionSchema:
    return AcceptanceCriterionSchema(given=given, when=when, then=then)


def _story(
    *,
    role: str = "SMB customer",
    action: str = "order the bundle",
    value: str = "I can use the service",
    criteria: list[AcceptanceCriterionSchema] | None = None,
) -> StoryItemSchema:
    return StoryItemSchema(
        role=role,
        action=action,
        value=value,
        acceptance_criteria=[_criterion()] if criteria is None else criteria,
    )


def test_valid_story_response_is_trimmed_and_carries_provenance() -> None:
    candidates = to_story_candidates(
        StorySetSchema(stories=[_story(role="  SMB customer  ")]),
        model="local-model",
        prompt_version="story-generation-v1",
    )

    assert candidates[0]["role"] == "SMB customer"
    assert candidates[0]["model"] == "local-model"
    assert candidates[0]["prompt_version"] == "story-generation-v1"


@pytest.mark.parametrize("field", ["role", "action", "value"])
def test_any_blank_story_field_rejects_the_complete_provider_response(field: str) -> None:
    invalid = _story(**{field: "   "})  # type: ignore[arg-type]

    with pytest.raises(StoryGenerationError, match="blank content in Story 2"):
        to_story_candidates(
            StorySetSchema(stories=[_story(), invalid]),
            model="model",
            prompt_version="prompt",
        )


def test_missing_acceptance_criteria_rejects_the_complete_provider_response() -> None:
    invalid = _story().model_copy(update={"acceptance_criteria": []})
    with pytest.raises(StoryGenerationError, match="no acceptance criteria"):
        to_story_candidates(
            StorySetSchema(stories=[_story(), invalid]),
            model="model",
            prompt_version="prompt",
        )


@pytest.mark.parametrize("field", ["given", "when", "then"])
def test_incomplete_criterion_rejects_the_complete_provider_response(field: str) -> None:
    values = {"given": "given", "when": "when", "then": "then"}
    values[field] = " "
    invalid_criterion = AcceptanceCriterionSchema(**values)

    with pytest.raises(StoryGenerationError, match="incomplete acceptance criterion"):
        to_story_candidates(
            StorySetSchema(stories=[_story(criteria=[invalid_criterion])]),
            model="model",
            prompt_version="prompt",
        )


def test_empty_story_set_is_a_provider_failure() -> None:
    with pytest.raises(StoryGenerationError, match="no Stories"):
        to_story_candidates(
            StorySetSchema.model_construct(stories=[]), model="model", prompt_version="prompt"
        )


@pytest.mark.parametrize("criteria", [None, []])
def test_provider_schema_requires_nonempty_acceptance_criteria(
    criteria: list[dict[str, str]] | None,
) -> None:
    payload: dict[str, object] = {"role": "customer", "action": "order", "value": "use service"}
    if criteria is not None:
        payload["acceptance_criteria"] = criteria
    with pytest.raises(ValidationError):
        StorySetSchema.model_validate({"stories": [payload]})
    schema = StorySetSchema.model_json_schema()
    story_schema = schema["$defs"]["StoryItemSchema"]
    assert "acceptance_criteria" in story_schema["required"]
    assert story_schema["properties"]["acceptance_criteria"]["minItems"] == 1


def _context() -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    requirement, analysis, epic, feature = (MagicMock() for _ in range(4))
    requirement.title.value = "Bundle ordering"
    requirement.description.value = "Allow eligible customers to order the bundle"
    analysis.known_facts = []
    analysis.constraints = []
    analysis.business_rules = []
    analysis.assumptions = []
    analysis.open_questions = []
    analysis.clarifications = []
    epic.name.value = "SMB bundle"
    epic.outcome.value = "Customers can order"
    feature.name.value = "Eligible ordering"
    feature.outcome.value = "Eligible orders are accepted"
    return requirement, analysis, epic, feature


def _story_set(count: int) -> StorySetSchema:
    return StorySetSchema(
        stories=[_story(action=f"complete split part {index + 1}") for index in range(count)]
    )


def _source_story() -> MagicMock:
    source = MagicMock()
    source.voice = "As a customer, I want complete the flow, so that I receive value."
    source.acceptance_criteria = []
    return source


@patch("smb_requirement_agent.infrastructure.llm.openai_adapters.OpenAI")
def test_openai_story_provider_exception_is_mapped(mock_openai: MagicMock) -> None:
    client = MagicMock()
    client.chat.completions.parse.side_effect = OpenAIError("boom")
    mock_openai.return_value = client

    with pytest.raises(StoryGenerationError, match="Story generation failed"):
        OpenAIStoryGenerator(
            mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
        ).generate(*_context())


@patch("smb_requirement_agent.infrastructure.llm.openai_adapters.OpenAI")
def test_openai_story_empty_choices_is_a_provider_failure(mock_openai: MagicMock) -> None:
    client = MagicMock()
    client.chat.completions.parse.return_value.choices = []
    mock_openai.return_value = client

    with pytest.raises(StoryGenerationError, match="no choices"):
        OpenAIStoryGenerator(
            mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
        ).generate(*_context())


@patch("smb_requirement_agent.infrastructure.llm.openai_adapters.OpenAI")
def test_openai_story_split_rejects_one_candidate(mock_openai: MagicMock) -> None:
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.parsed = _story_set(1)
    client.chat.completions.parse.return_value = response
    mock_openai.return_value = client

    with pytest.raises(StoryGenerationError, match="fewer than two split candidates"):
        OpenAIStoryGenerator(
            mock_openai.return_value, model="gpt-4o", timeout_seconds=60.0
        ).propose_split(*_context(), _source_story())


@patch.object(
    LocalStructuredOutputClient,
    "parse",
    side_effect=LocalLLMError("local provider failed"),
)
def test_local_story_provider_exception_is_mapped(_parse: MagicMock) -> None:
    generator = LocalStoryGenerator(
        base_url="http://127.0.0.1:11434/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=1,
        reasoning_effort=None,
    )

    with pytest.raises(StoryGenerationError, match="Local LLM Story generation failed"):
        generator.generate(*_context())


@patch.object(LocalStructuredOutputClient, "parse")
def test_local_story_split_retries_one_candidate_with_corrective_prompt(
    parse: MagicMock,
) -> None:
    parse.side_effect = [_story_set(1), _story_set(2)]
    generator = LocalStoryGenerator(
        base_url="http://127.0.0.1:11434/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=1,
        reasoning_effort=None,
    )

    candidates = generator.propose_split(*_context(), _source_story())

    assert len(candidates) == 2
    assert all(candidate["prompt_version"] == PROMPT_VERSION for candidate in candidates)
    assert parse.call_count == 2
    retry_prompt = parse.call_args_list[1].kwargs["user_prompt"]
    assert "previous split response contained fewer than two Stories" in retry_prompt


@patch.object(LocalStructuredOutputClient, "parse")
def test_local_story_split_fails_when_corrective_retry_is_still_short(
    parse: MagicMock,
) -> None:
    parse.side_effect = [_story_set(1), _story_set(1)]
    generator = LocalStoryGenerator(
        base_url="http://127.0.0.1:11434/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=1,
        reasoning_effort=None,
    )

    with pytest.raises(StoryGenerationError, match="after one corrective retry"):
        generator.propose_split(*_context(), _source_story())


@patch.object(LocalStructuredOutputClient, "parse")
def test_correction_separates_failed_ai_content_from_business_evidence(parse: MagicMock) -> None:
    parse.return_value = _story_set(2)
    with httpx.Client() as client:
        generator = LocalStoryGenerator(
            base_url="http://127.0.0.1:11434/v1",
            http_client=client,
            model="local-model",
            timeout_seconds=1,
            reasoning_effort=None,
        )
        generator.generate(
            *_context(),
            guidance=GenerationGuidance(
                feedback=("small: split audit and approval",),
                previous_draft=("Require an invented five-minute approval",),
                potential_dependencies=("Unconfirmed catalogue dependency",),
                minimum_story_count=2,
            ),
        )
    prompt = parse.call_args.kwargs["user_prompt"]
    before, correction = prompt.split("APPLICATION CORRECTION TASK")
    assert "invented five-minute approval" not in before
    assert "Unconfirmed catalogue dependency" in before
    assert "return at least 2 Stories" in correction
    assert "FAILED DRAFT (AI output, not confirmed business evidence)" in correction
    assert "Remove invented details" in correction
    assert "small: split audit and approval" in correction


def test_quality_prompt_distinguishes_confirmed_policy_from_unknowns() -> None:
    prompt = build_story_quality_prompt(
        _source_story(),
        (),
        (InvestCriterion.ESTIMABLE,),
        evidence=StoryQualityEvidence(
            source_facts=("Audit customer input.",),
            human_decisions=("Audit criteria are unspecified.",),
            unconfirmed=("Possibly block suspicious submissions.",),
        ),
    )
    assert '"human_decisions": ["Audit criteria are unspecified."]' in prompt
    assert '"unconfirmed": ["Possibly block suspicious submissions."]' in prompt
    assert "SOURCE FACTS" in prompt
