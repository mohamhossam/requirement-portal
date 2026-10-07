"""Knowledge embedding and relationship adapters reject anything they cannot trust.

A vector with the wrong shape, a non-finite number or a missing entry would
silently corrupt search, and a classifier finding without citations would reach
a person as unsupported evidence. Each adapter must turn those into
`KnowledgeGenerationError`, never into stored data.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from types import SimpleNamespace
from typing import Any, TypeVar, cast
from unittest.mock import MagicMock

import httpx
import pytest
from openai import OpenAI, OpenAIError
from pydantic import BaseModel
from smb_kernel.llm.structured_output import StructuredOutputError

from smb_requirement_agent.application.errors import KnowledgeGenerationError
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
    KnowledgeRelationshipKind,
    KnowledgeSourceKind,
)
from smb_requirement_agent.infrastructure.llm.requirement_knowledge_adapters import (
    EMBEDDING_DIMENSIONS,
    LocalKnowledgeEmbedding,
    OpenAIKnowledgeEmbedding,
    StructuredClarificationAnswerSuggesterAdapter,
    StructuredRequirementRelationshipClassifierAdapter,
)
from smb_requirement_agent.infrastructure.llm.schemas.knowledge_schema import (
    AnswerSuggestionListSchema,
    AnswerSuggestionSchema,
    RelationshipFindingSchema,
    RelationshipScreenSchema,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

SchemaT = TypeVar("SchemaT", bound=BaseModel)
VECTOR = [0.5] * EMBEDDING_DIMENSIONS


def _local(handler: Callable[[httpx.Request], httpx.Response]) -> LocalKnowledgeEmbedding:
    return LocalKnowledgeEmbedding(
        "http://embeddings.test/v1",
        "local-embedding",
        5,
        httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _returning(body: object) -> Callable[[httpx.Request], httpx.Response]:
    return lambda request: httpx.Response(200, json=body)


def test_local_embedding_orders_vectors_by_index() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        first, second = [0.1] * EMBEDDING_DIMENSIONS, [0.2] * EMBEDDING_DIMENSIONS
        return httpx.Response(
            200,
            json={"data": [{"index": 1, "embedding": second}, {"index": 0, "embedding": first}]},
        )

    vectors = _local(handler).embed(("first", "second"))

    assert [vector[0] for vector in vectors] == [0.1, 0.2]
    assert requests == [{"model": "local-embedding", "input": ["first", "second"]}]


def test_no_text_means_no_embedding_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No request expected.")

    assert _local(handler).embed(()) == ()


@pytest.mark.parametrize(
    ("handler", "message"),
    [
        pytest.param(lambda request: httpx.Response(500), "embedding failed", id="status"),
        pytest.param(lambda request: httpx.Response(200, content=b"<html>"), "failed", id="json"),
        pytest.param(_returning(["not", "an", "object"]), "invalid data", id="payload"),
        pytest.param(_returning({"data": "vectors"}), "invalid data", id="data"),
        pytest.param(_returning({"data": [{"vector": VECTOR}]}), "invalid vectors", id="entry"),
        pytest.param(
            _returning({"data": [{"embedding": ["a"] * EMBEDDING_DIMENSIONS}]}),
            "non-numeric",
            id="numeric",
        ),
        pytest.param(
            _returning({"data": [{"embedding": VECTOR}, {"embedding": VECTOR}]}),
            "2 vectors for 1 inputs",
            id="count",
        ),
        pytest.param(_returning({"data": [{"embedding": [0.5] * 3}]}), "dimensions", id="width"),
        pytest.param(
            lambda request: httpx.Response(
                200,
                content=b'{"data": [{"embedding": [NaN'
                + b", 0.5" * (EMBEDDING_DIMENSIONS - 1)
                + b"]}]}",
            ),
            "finite",
            id="finite",
        ),
    ],
)
def test_local_embedding_rejects_untrustworthy_responses(
    handler: Callable[[httpx.Request], httpx.Response], message: str
) -> None:
    with pytest.raises(KnowledgeGenerationError, match=message):
        _local(handler).embed(("text",))


def test_openai_embedding_orders_vectors_and_requests_the_fixed_width() -> None:
    client = MagicMock()
    client.embeddings.create.return_value = SimpleNamespace(
        data=[
            SimpleNamespace(index=1, embedding=[0.2] * EMBEDDING_DIMENSIONS),
            SimpleNamespace(index=0, embedding=[0.1] * EMBEDDING_DIMENSIONS),
        ]
    )
    adapter = OpenAIKnowledgeEmbedding(cast(OpenAI, client), "text-embedding-3-small")

    vectors = adapter.embed(("first", "second"))

    assert [vector[0] for vector in vectors] == [0.1, 0.2]
    client.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small",
        input=["first", "second"],
        dimensions=EMBEDDING_DIMENSIONS,
    )
    assert adapter.embed(()) == ()


def test_openai_embedding_failure_is_a_knowledge_generation_error() -> None:
    client = MagicMock()
    client.embeddings.create.side_effect = OpenAIError("quota exceeded")
    adapter = OpenAIKnowledgeEmbedding(cast(OpenAI, client), "text-embedding-3-small")

    with pytest.raises(KnowledgeGenerationError, match="quota exceeded"):
        adapter.embed(("text",))


class _Client:
    """A `StructuredOutputClient` returning one prepared result or raising."""

    model = "structured-model"

    def __init__(self, result: BaseModel | Exception) -> None:
        self._result = result

    def parse(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_type: type[SchemaT],
        images: Sequence[tuple[str, bytes]] = (),
    ) -> SchemaT:
        if isinstance(self._result, Exception):
            raise self._result
        assert isinstance(self._result, schema_type)
        return self._result


def _requirement() -> Requirement:
    return Requirement(
        RequirementId("subject"),
        RequirementTitle("Refunds"),
        RequirementDescription("Refund within five days."),
        RequirementStatus.DRAFT,
    )


def _finding(
    related: str = "related", rationale: str = "Opposing rule.", cited: tuple[str, ...] = ("c1",)
) -> RelationshipFindingSchema:
    return RelationshipFindingSchema(
        related_requirement_id=related,
        relation="possible_contradiction",
        rationale=rationale,
        cited_chunk_ids=list(cited),
    )


def _classify(result: BaseModel | Exception) -> object:
    adapter = StructuredRequirementRelationshipClassifierAdapter(_Client(result), "Test")
    return adapter.classify(_requirement(), "Refund within five days.", ())


def test_the_classifier_maps_cited_findings() -> None:
    (candidate,) = cast(
        tuple[Any, ...], _classify(RelationshipScreenSchema(findings=[_finding(cited=(" c1 ",))]))
    )

    assert candidate.related_requirement_id == RequirementId("related")
    assert candidate.kind is KnowledgeRelationshipKind.POSSIBLE_CONTRADICTION
    assert candidate.cited_chunk_ids == ("c1",)


@pytest.mark.parametrize(
    ("result", "message"),
    [
        pytest.param(StructuredOutputError("timeout"), "classification failed", id="provider"),
        pytest.param(
            RelationshipScreenSchema(findings=[_finding(rationale="  ")]), "incomplete", id="blank"
        ),
        pytest.param(
            RelationshipScreenSchema(findings=[_finding(), _finding()]), "incomplete", id="repeat"
        ),
        pytest.param(
            RelationshipScreenSchema(findings=[_finding(cited=("c1", "c1"))]),
            "duplicate citations",
            id="citations",
        ),
    ],
)
def test_the_classifier_rejects_unsupported_findings(
    result: BaseModel | Exception, message: str
) -> None:
    with pytest.raises(KnowledgeGenerationError, match=message):
        _classify(result)


def test_the_suggester_rejects_a_suggestion_citing_one_passage_twice() -> None:
    chunk = KnowledgeChunk(
        KnowledgeChunkId("c1"),
        RequirementId("subject"),
        1,
        KnowledgeSourceKind.CURRENT_ANALYSIS,
        "business_rule",
        "Refund within five days.",
        "fingerprint-c1",
        "/requirements/subject/clarify",
    )
    question = ClarificationQuestion(
        QuestionId("question-1"),
        RequirementId("subject"),
        AnalysisId("analysis-1"),
        ClarificationKind.OPEN_QUESTION,
        "How fast are refunds?",
        "The refund window must be confirmed.",
        ClarificationSeverity.HIGH,
        True,
        ClarificationSource.AI,
    )
    result = AnswerSuggestionListSchema(
        suggestions=[
            AnswerSuggestionSchema(
                answer="Five days.", rationale="Stated rule.", cited_evidence_numbers=[1, 1]
            )
        ]
    )
    adapter = StructuredClarificationAnswerSuggesterAdapter(_Client(result), "Test")

    with pytest.raises(KnowledgeGenerationError, match="duplicate citations"):
        adapter.suggest(_requirement(), question, (chunk,), ())
