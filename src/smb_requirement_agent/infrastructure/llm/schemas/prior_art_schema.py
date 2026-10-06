"""Strict structured output of the prior-art judge (Knowledge Center E2)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PriorArtMatchSchema(_Strict):
    candidate_number: PositiveInt
    verdict: Literal["similar_past_requirement"]
    rationale: str = Field(min_length=1)
    cited_evidence_numbers: list[PositiveInt] = Field(min_length=1, max_length=5)


class PriorArtJudgementSchema(_Strict):
    matches: list[PriorArtMatchSchema] = Field(max_length=5)
