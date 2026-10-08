"""Structured-output schema for semantic INVEST review."""

from typing import Literal

from pydantic import BaseModel, Field


class InvestFindingSchema(BaseModel):
    criterion: Literal["independent", "negotiable", "valuable", "estimable", "small"]
    message: str = Field(description="Concise evidence or actionable problem.")
    passed: bool = Field(description="Verdict consistent with the evidence in message.")


class StoryQualitySchema(BaseModel):
    findings: list[InvestFindingSchema] = Field(default_factory=list)
