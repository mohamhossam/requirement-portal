"""Strict structured-output schemas for requirement knowledge operations."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RelationshipFindingSchema(_Strict):
    related_requirement_id: str = Field(min_length=1)
    relation: Literal["possible_duplicate", "possible_contradiction"]
    rationale: str = Field(min_length=1)
    cited_chunk_ids: list[str] = Field(min_length=1, max_length=5)


class RelationshipScreenSchema(_Strict):
    findings: list[RelationshipFindingSchema] = Field(max_length=10)


# The model is shown these limits but not held to them: a fourth answer or a sixth
# citation is trimmed by the adapter rather than failing the whole suggestion.
SUGGESTION_LIMIT = 3
SUGGESTION_CITATION_LIMIT = 5


class AnswerSuggestionSchema(_Strict):
    answer: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    cited_evidence_numbers: list[PositiveInt] = Field(
        min_length=1, json_schema_extra={"maxItems": SUGGESTION_CITATION_LIMIT}
    )


class AnswerSuggestionListSchema(_Strict):
    suggestions: list[AnswerSuggestionSchema] = Field(
        json_schema_extra={"maxItems": SUGGESTION_LIMIT}
    )
