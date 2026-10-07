"""Contract tests for grounded-answer provider adapters."""

from __future__ import annotations

import json
from typing import cast
from unittest.mock import MagicMock, patch

import httpx
import pytest
from smb_kernel.llm.structured_output import StructuredOutputError

from smb_requirement_agent.application.errors import KnowledgeGenerationError
from smb_requirement_agent.application.ports.reference_grounding import ReferenceEvidence
from smb_requirement_agent.domain.analysis.entities import ClarificationQuestion
from smb_requirement_agent.domain.analysis.value_objects import (
    AnalysisId,
    ClarificationKind,
    ClarificationSeverity,
    ClarificationSource,
    QuestionId,
)
from smb_requirement_agent.domain.knowledge.entities import (
    KnowledgeChunk,
    KnowledgeChunkId,
    KnowledgeMatch,
    KnowledgeSourceKind,
)
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.infrastructure.llm.prompts.knowledge_prompt import (
    SUGGESTION_SYSTEM_PROMPT,
    suggestion_prompt,
)
from smb_requirement_agent.infrastructure.llm.requirement_knowledge_adapters import (
    LocalClarificationAnswerSuggester,
    LocalRequirementRelationshipClassifier,
)
from smb_requirement_agent.infrastructure.llm.schemas.knowledge_schema import (
    AnswerSuggestionListSchema,
    AnswerSuggestionSchema,
)
from smb_requirement_agent.shared_kernel.citation import PublishedReference
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


def _requirement() -> Requirement:
    return Requirement(
        RequirementId("subject-requirement"),
        RequirementTitle("XGPON ordering"),
        RequirementDescription("Prepare the XGPON bundle launch."),
        RequirementStatus.DRAFT,
    )


def _question() -> ClarificationQuestion:
    return ClarificationQuestion(
        QuestionId("question-1"),
        RequirementId("subject-requirement"),
        AnalysisId("analysis-1"),
        ClarificationKind.OPEN_QUESTION,
        "Which ordering channels are supported?",
        "The supported channel scope must be confirmed.",
        ClarificationSeverity.HIGH,
        True,
        ClarificationSource.AI,
    )


def _chunk(
    chunk_id: str,
    requirement_id: str,
    source_kind: KnowledgeSourceKind,
    text: str,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        KnowledgeChunkId(chunk_id),
        RequirementId(requirement_id),
        1,
        source_kind,
        "business_rule",
        text,
        f"fingerprint-{chunk_id}",
        f"/requirements/{requirement_id}/clarify",
    )


def _adapter() -> LocalClarificationAnswerSuggester:
    return LocalClarificationAnswerSuggester(
        base_url="http://127.0.0.1:1234/v1",
        http_client=cast(httpx.Client, MagicMock()),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        context_window_tokens=8192,
        max_output_tokens=2048,
    )


@pytest.mark.parametrize("mode", ["valid", "empty", "blank", "unknown", "provider"])
@patch(
    "smb_requirement_agent.infrastructure.llm.requirement_knowledge_adapters.LocalStructuredOutputClient"
)
def test_reference_answer_contract(client_type: MagicMock, mode: str) -> None:
    citation = PublishedReference(
        "doc",
        "Policy",
        "file",
        1,
        "rev",
        "pub",
        "a" * 64,
        "block",
        "Line 1",
        "Coverage required.",
        0,
        18,
        "b" * 64,
    )
    references = (ReferenceEvidence(citation, "Approved surrounding context", ("Line 1",)),)
    client_type.return_value.parse.return_value = AnswerSuggestionListSchema(
        suggestions=[]
        if mode == "empty"
        else [
            AnswerSuggestionSchema(
                answer="  " if mode == "blank" else "Coverage required.",
                rationale="The exact passage supports this answer.",
                cited_evidence_numbers=[2 if mode == "unknown" else 1],
            )
        ]
    )
    if mode == "provider":
        client_type.return_value.parse.side_effect = StructuredOutputError("Offline")
    if mode in {"blank", "unknown", "provider"}:
        with pytest.raises(KnowledgeGenerationError):
            _adapter().suggest(_requirement(), _question(), (), (), references)
    else:
        result = _adapter().suggest(_requirement(), _question(), (), (), references)
        assert result[0].cited_chunk_ids == ("reference:0",) if mode == "valid" else result == ()
        prompt = json.loads(client_type.return_value.parse.call_args.kwargs["user_prompt"])
        assert prompt["published_reference_evidence"][0]["exact_excerpt"] == citation.excerpt
        assert prompt["published_reference_evidence"][0]["evidence_number"] == 1


@pytest.mark.parametrize(
    "adapter_type",
    [LocalRequirementRelationshipClassifier, LocalClarificationAnswerSuggester],
)
@patch(
    "smb_requirement_agent.infrastructure.llm.requirement_knowledge_adapters."
    "LocalStructuredOutputClient"
)
def test_local_knowledge_adapters_reserve_a_bounded_output_budget(
    client_type: MagicMock,
    adapter_type: type[LocalRequirementRelationshipClassifier | LocalClarificationAnswerSuggester],
) -> None:
    adapter_type(
        base_url="http://127.0.0.1:1234/v1",
        http_client=cast(httpx.Client, MagicMock()),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        context_window_tokens=16384,
        max_output_tokens=8192,
    )

    assert client_type.call_args.kwargs["max_output_tokens"] == 2048


def test_local_suggester_accepts_ranked_evidence_that_needs_more_than_half_of_16k_context() -> None:
    http_client = MagicMock(spec=httpx.Client)
    http_client.post.return_value.json.return_value = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": '{"suggestions":[]}'},
            }
        ]
    }
    adapter = LocalClarificationAnswerSuggester(
        base_url="http://127.0.0.1:1234/v1",
        http_client=cast(httpx.Client, http_client),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        context_window_tokens=16384,
        max_output_tokens=8192,
    )
    matches = tuple(
        KnowledgeMatch(
            _chunk(
                f"{index:064x}",
                f"trusted-requirement-{index}",
                KnowledgeSourceKind.CONFIRMED_ANALYSIS,
                f"Evidence {index}: " + "supported detail " * 115,
            )
        )
        for index in range(20)
    )
    prompt = suggestion_prompt(_requirement(), _question(), (), matches)
    schema_text = json.dumps(AnswerSuggestionListSchema.model_json_schema(), separators=(",", ":"))
    estimated_input_tokens = (
        len(SUGGESTION_SYSTEM_PROMPT) + len(prompt) + len(schema_text) + 3
    ) // 4
    assert 8192 < estimated_input_tokens < 14336

    assert adapter.suggest(_requirement(), _question(), (), matches) == ()
    assert http_client.post.call_args.kwargs["json"]["max_tokens"] == 2048


@patch(
    "smb_requirement_agent.infrastructure.llm.requirement_knowledge_adapters."
    "LocalStructuredOutputClient"
)
def test_local_answer_suggester_uses_short_evidence_numbers_and_restores_chunk_ids(
    client_type: MagicMock,
) -> None:
    client_type.return_value.parse.return_value = AnswerSuggestionListSchema(
        suggestions=[
            AnswerSuggestionSchema(
                answer="Use BCRM and CPP.",
                rationale="Both supplied sources support these channels.",
                cited_evidence_numbers=[1, 2],
            )
        ]
    )
    current = _chunk(
        "a" * 64,
        "subject-requirement",
        KnowledgeSourceKind.CURRENT_ANALYSIS,
        "BCRM is in scope.",
    )
    trusted = _chunk(
        "b" * 64,
        "trusted-requirement",
        KnowledgeSourceKind.CONFIRMED_ANALYSIS,
        "CPP is an approved ordering channel.",
    )

    result = _adapter().suggest(_requirement(), _question(), (current,), (KnowledgeMatch(trusted),))

    assert result[0].cited_chunk_ids == (current.id.value, trusted.id.value)
    prompt = json.loads(client_type.return_value.parse.call_args.kwargs["user_prompt"])
    assert prompt["current_analysis_evidence"][0]["evidence_number"] == 1
    assert prompt["trusted_knowledge_evidence"][0]["evidence_number"] == 2
    assert "chunk_id" not in prompt["current_analysis_evidence"][0]
    assert current.id.value not in client_type.return_value.parse.call_args.kwargs["user_prompt"]


@patch(
    "smb_requirement_agent.infrastructure.llm.requirement_knowledge_adapters."
    "LocalStructuredOutputClient"
)
def test_local_answer_suggester_rejects_an_out_of_range_evidence_number(
    client_type: MagicMock,
) -> None:
    client_type.return_value.parse.return_value = AnswerSuggestionListSchema(
        suggestions=[
            AnswerSuggestionSchema(
                answer="Use BCRM.",
                rationale="Supported by evidence.",
                cited_evidence_numbers=[2],
            )
        ]
    )
    current = _chunk(
        "a" * 64,
        "subject-requirement",
        KnowledgeSourceKind.CURRENT_ANALYSIS,
        "BCRM is in scope.",
    )

    with pytest.raises(KnowledgeGenerationError, match="outside the supplied candidates"):
        _adapter().suggest(_requirement(), _question(), (current,), ())
