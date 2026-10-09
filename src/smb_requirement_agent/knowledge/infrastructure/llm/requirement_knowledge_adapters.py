"""OpenAI and local OpenAI-compatible requirement-knowledge adapters."""

from __future__ import annotations

import math

import httpx
from openai import OpenAI, OpenAIError
from pydantic import ValidationError
from smb_kernel.diagnostics import DebugTrace, NullDebugTrace
from smb_kernel.llm.local_structured_output import (
    LocalStructuredOutputClient,
)
from smb_kernel.llm.structured_output import (
    StructuredOutputClient,
    StructuredOutputError,
)

from smb_requirement_agent.analysis.domain.entities import ClarificationQuestion
from smb_requirement_agent.application.errors import KnowledgeGenerationError
from smb_requirement_agent.knowledge.application.ports.prior_art import (
    PriorArtCandidateInput,
    PriorArtJudgement,
)
from smb_requirement_agent.knowledge.application.ports.requirement_knowledge import (
    AnswerSuggestionCandidate,
    Embedding,
    RelationshipCandidate,
)
from smb_requirement_agent.knowledge.domain.entities import (
    KnowledgeChunk,
    KnowledgeMatch,
    KnowledgeRelationshipKind,
)
from smb_requirement_agent.knowledge.infrastructure.llm.prompts.knowledge_prompt import (
    RELATIONSHIP_SYSTEM_PROMPT,
    SCREEN_PROMPT_VERSION,
    SUGGESTION_PROMPT_VERSION,
    SUGGESTION_SYSTEM_PROMPT,
    relationship_prompt,
    suggestion_prompt,
)
from smb_requirement_agent.knowledge.infrastructure.llm.prompts.prior_art_prompt import (
    PRIOR_ART_PROMPT_VERSION,
    PRIOR_ART_SYSTEM_PROMPT,
    prior_art_prompt,
)
from smb_requirement_agent.knowledge.infrastructure.llm.schemas.knowledge_schema import (
    AnswerSuggestionListSchema,
    RelationshipScreenSchema,
)
from smb_requirement_agent.knowledge.infrastructure.llm.schemas.prior_art_schema import (
    PriorArtJudgementSchema,
)
from smb_requirement_agent.references.application.ports.reference_grounding import ReferenceEvidence
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

EMBEDDING_DIMENSIONS = 768
LOCAL_KNOWLEDGE_MAX_OUTPUT_TOKENS = 2048


class OpenAIKnowledgeEmbedding:
    def __init__(self, client: OpenAI, model: str) -> None:
        self._client = client
        self.model = model

    def embed(self, texts: tuple[str, ...]) -> tuple[Embedding, ...]:
        if not texts:
            return ()
        try:
            response = self._client.embeddings.create(
                model=self.model,
                input=list(texts),
                dimensions=EMBEDDING_DIMENSIONS,
            )
        except (OpenAIError, ValidationError) as exc:
            raise KnowledgeGenerationError(f"Knowledge embedding failed: {exc}") from exc
        ordered = sorted(response.data, key=lambda item: item.index)
        return _validate_embeddings(tuple(tuple(item.embedding) for item in ordered), len(texts))


class LocalKnowledgeEmbedding:
    def __init__(
        self, base_url: str, model: str, timeout_seconds: float, http_client: httpx.Client
    ) -> None:
        self._endpoint = f"{base_url.rstrip('/')}/embeddings"
        self._timeout_seconds = timeout_seconds
        self._http = http_client
        self.model = model

    def embed(self, texts: tuple[str, ...]) -> tuple[Embedding, ...]:
        if not texts:
            return ()
        try:
            response = self._http.post(
                self._endpoint,
                json={"model": self.model, "input": list(texts)},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise KnowledgeGenerationError(f"Local knowledge embedding failed: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise KnowledgeGenerationError("Local embedding provider returned invalid data.")
        raw = payload["data"]
        values: list[tuple[int, Embedding]] = []
        for item in raw:
            if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
                raise KnowledgeGenerationError("Local embedding provider returned invalid vectors.")
            try:
                embedding = tuple(float(value) for value in item["embedding"])
                index = int(item.get("index", len(values)))
            except (TypeError, ValueError) as exc:
                raise KnowledgeGenerationError(
                    "Local embedding provider returned non-numeric vectors."
                ) from exc
            values.append((index, embedding))
        return _validate_embeddings(tuple(value for _, value in sorted(values)), len(texts))


class OpenRouterKnowledgeEmbedding:
    def __init__(
        self,
        *,
        base_url: str,
        http_client: httpx.Client,
        api_key: str,
        model: str,
        timeout_seconds: float,
        data_collection: str,
    ) -> None:
        self._endpoint = f"{base_url.rstrip('/')}/embeddings"
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._data_collection = data_collection
        self._http = http_client
        self.model = model

    def embed(self, texts: tuple[str, ...]) -> tuple[Embedding, ...]:
        if not texts:
            return ()
        try:
            response = self._http.post(
                self._endpoint,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": list(texts),
                    "dimensions": EMBEDDING_DIMENSIONS,
                    "provider": {"data_collection": self._data_collection},
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise KnowledgeGenerationError(f"OpenRouter knowledge embedding failed: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise KnowledgeGenerationError("OpenRouter embedding provider returned invalid data.")
        if len(payload["data"]) != len(texts):
            vector_count = len(payload["data"])
            raise KnowledgeGenerationError(
                f"Embedding provider returned {vector_count} vectors for {len(texts)} texts."
            )
        values: list[tuple[int, Embedding]] = []
        for item in payload["data"]:
            if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
                raise KnowledgeGenerationError(
                    "OpenRouter embedding provider returned invalid vectors."
                )
            index = item.get("index")
            if not isinstance(index, int) or isinstance(index, bool):
                raise KnowledgeGenerationError(
                    "OpenRouter embedding provider returned invalid vector indices."
                )
            try:
                embedding = tuple(float(value) for value in item["embedding"])
            except (TypeError, ValueError) as exc:
                raise KnowledgeGenerationError(
                    "OpenRouter embedding provider returned non-numeric vectors."
                ) from exc
            values.append((index, embedding))
        if sorted(index for index, _ in values) != list(range(len(texts))):
            raise KnowledgeGenerationError(
                "OpenRouter embedding provider returned invalid vector indices."
            )
        return _validate_embeddings(tuple(value for _, value in sorted(values)), len(texts))


class StructuredRequirementRelationshipClassifierAdapter:
    prompt_version = SCREEN_PROMPT_VERSION

    def __init__(self, client: StructuredOutputClient, provider_name: str) -> None:
        self._client = client
        self._provider_name = provider_name
        self.model = client.model

    def classify(
        self,
        requirement: Requirement,
        subject_text: str,
        matches: tuple[KnowledgeMatch, ...],
    ) -> tuple[RelationshipCandidate, ...]:
        try:
            result = self._client.parse(
                system_prompt=RELATIONSHIP_SYSTEM_PROMPT,
                user_prompt=relationship_prompt(requirement, subject_text, matches),
                schema_type=RelationshipScreenSchema,
            )
        except StructuredOutputError as exc:
            raise KnowledgeGenerationError(
                f"{self._provider_name} knowledge classification failed: {exc}"
            ) from exc
        return _relationships(result)


class LocalRequirementRelationshipClassifier(StructuredRequirementRelationshipClassifierAdapter):
    def __init__(
        self,
        *,
        base_url: str,
        http_client: httpx.Client,
        model: str,
        timeout_seconds: float,
        reasoning_effort: str | None,
        context_window_tokens: int,
        max_output_tokens: int,
        debug_trace: DebugTrace | None = None,
    ) -> None:
        super().__init__(
            LocalStructuredOutputClient(
                base_url=base_url,
                http_client=http_client,
                model=model,
                timeout_seconds=timeout_seconds,
                reasoning_effort=reasoning_effort,
                context_window_tokens=context_window_tokens,
                max_output_tokens=min(max_output_tokens, LOCAL_KNOWLEDGE_MAX_OUTPUT_TOKENS),
                debug_trace=debug_trace if debug_trace is not None else NullDebugTrace(),
            ),
            "Local",
        )


class StructuredPriorArtJudge:
    """The prior-art judge on any structured-output client (Knowledge Center E2)."""

    prompt_version = PRIOR_ART_PROMPT_VERSION

    def __init__(self, client: StructuredOutputClient, provider_name: str) -> None:
        self._client = client
        self._provider_name = provider_name
        self.model = client.model

    def judge(
        self, title: str, subject_text: str, candidates: tuple[PriorArtCandidateInput, ...]
    ) -> tuple[PriorArtJudgement, ...]:
        try:
            result = self._client.parse(
                system_prompt=PRIOR_ART_SYSTEM_PROMPT,
                user_prompt=prior_art_prompt(title, subject_text, candidates),
                schema_type=PriorArtJudgementSchema,
            )
        except StructuredOutputError as exc:
            raise KnowledgeGenerationError(
                f"{self._provider_name} prior-art judgement failed: {exc}"
            ) from exc
        return tuple(
            PriorArtJudgement(
                match.candidate_number,
                match.rationale.strip(),
                tuple(match.cited_evidence_numbers),
            )
            for match in result.matches
        )


class LocalPriorArtJudge(StructuredPriorArtJudge):
    def __init__(
        self,
        *,
        base_url: str,
        http_client: httpx.Client,
        model: str,
        timeout_seconds: float,
        reasoning_effort: str | None,
        context_window_tokens: int,
        max_output_tokens: int,
        debug_trace: DebugTrace | None = None,
    ) -> None:
        super().__init__(
            LocalStructuredOutputClient(
                base_url=base_url,
                http_client=http_client,
                model=model,
                timeout_seconds=timeout_seconds,
                reasoning_effort=reasoning_effort,
                context_window_tokens=context_window_tokens,
                max_output_tokens=min(max_output_tokens, LOCAL_KNOWLEDGE_MAX_OUTPUT_TOKENS),
                debug_trace=debug_trace if debug_trace is not None else NullDebugTrace(),
            ),
            "Local",
        )


class StructuredClarificationAnswerSuggesterAdapter:
    prompt_version = SUGGESTION_PROMPT_VERSION

    def __init__(self, client: StructuredOutputClient, provider_name: str) -> None:
        self._client = client
        self._provider_name = provider_name
        self.model = client.model

    def suggest(
        self,
        requirement: Requirement,
        question: ClarificationQuestion,
        current_analysis: tuple[KnowledgeChunk, ...],
        matches: tuple[KnowledgeMatch, ...],
        references: tuple[ReferenceEvidence, ...] = (),
    ) -> tuple[AnswerSuggestionCandidate, ...]:
        try:
            result = self._client.parse(
                system_prompt=SUGGESTION_SYSTEM_PROMPT,
                user_prompt=suggestion_prompt(
                    requirement, question, current_analysis, matches, references
                ),
                schema_type=AnswerSuggestionListSchema,
            )
        except StructuredOutputError as exc:
            raise KnowledgeGenerationError(
                f"{self._provider_name} answer suggestion failed: {exc}"
            ) from exc
        return _suggestions(result, current_analysis, matches, references)


class LocalClarificationAnswerSuggester(StructuredClarificationAnswerSuggesterAdapter):
    def __init__(
        self,
        *,
        base_url: str,
        http_client: httpx.Client,
        model: str,
        timeout_seconds: float,
        reasoning_effort: str | None,
        context_window_tokens: int,
        max_output_tokens: int,
        debug_trace: DebugTrace | None = None,
    ) -> None:
        super().__init__(
            LocalStructuredOutputClient(
                base_url=base_url,
                http_client=http_client,
                model=model,
                timeout_seconds=timeout_seconds,
                reasoning_effort=reasoning_effort,
                context_window_tokens=context_window_tokens,
                max_output_tokens=min(max_output_tokens, LOCAL_KNOWLEDGE_MAX_OUTPUT_TOKENS),
                debug_trace=debug_trace if debug_trace is not None else NullDebugTrace(),
            ),
            "Local",
        )


def _relationships(result: RelationshipScreenSchema) -> tuple[RelationshipCandidate, ...]:
    values: list[RelationshipCandidate] = []
    seen: set[str] = set()
    for item in result.findings:
        requirement_id = item.related_requirement_id.strip()
        rationale = item.rationale.strip()
        citations = tuple(value.strip() for value in item.cited_chunk_ids if value.strip())
        if not requirement_id or not rationale or not citations or requirement_id in seen:
            raise KnowledgeGenerationError("Knowledge classifier returned incomplete findings.")
        if len(citations) != len(set(citations)):
            raise KnowledgeGenerationError("Knowledge classifier returned duplicate citations.")
        seen.add(requirement_id)
        values.append(
            RelationshipCandidate(
                RequirementId(requirement_id),
                KnowledgeRelationshipKind(item.relation),
                rationale,
                citations,
            )
        )
    return tuple(values)


def _suggestions(
    result: AnswerSuggestionListSchema,
    current_analysis: tuple[KnowledgeChunk, ...],
    matches: tuple[KnowledgeMatch, ...],
    references: tuple[ReferenceEvidence, ...] = (),
) -> tuple[AnswerSuggestionCandidate, ...]:
    supplied_evidence = (*current_analysis, *(match.chunk for match in matches))
    evidence_ids = tuple(item.id.value for item in supplied_evidence) + tuple(
        f"reference:{i}" for i in range(len(references))
    )
    values: list[AnswerSuggestionCandidate] = []
    seen: set[str] = set()
    for item in result.suggestions:
        answer = item.answer.strip()
        rationale = item.rationale.strip()
        citation_numbers = tuple(item.cited_evidence_numbers)
        if any(number < 1 or number > len(evidence_ids) for number in citation_numbers):
            raise KnowledgeGenerationError(
                "Answer suggester cited evidence outside the supplied candidates."
            )
        # In range: every number was checked against the evidence just above.
        citations = tuple(evidence_ids[number - 1] for number in citation_numbers)
        if not answer or not rationale or not citations or answer.casefold() in seen:
            raise KnowledgeGenerationError("Answer suggester returned incomplete suggestions.")
        if len(citations) != len(set(citations)):
            raise KnowledgeGenerationError("Answer suggester returned duplicate citations.")
        seen.add(answer.casefold())
        values.append(AnswerSuggestionCandidate(answer, rationale, citations))
    return tuple(values)


def _validate_embeddings(
    values: tuple[Embedding, ...], expected_count: int
) -> tuple[Embedding, ...]:
    if len(values) != expected_count:
        raise KnowledgeGenerationError(
            f"Embedding provider returned {len(values)} vectors for {expected_count} inputs."
        )
    if any(len(item) != EMBEDDING_DIMENSIONS for item in values):
        raise KnowledgeGenerationError(
            f"Knowledge embeddings must contain exactly {EMBEDDING_DIMENSIONS} dimensions."
        )
    if any(not math.isfinite(number) for item in values for number in item):
        raise KnowledgeGenerationError("Knowledge embeddings must contain finite numbers.")
    return values
