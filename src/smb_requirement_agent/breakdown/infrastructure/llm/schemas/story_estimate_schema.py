"""Structured-output schema for relative Story sizing."""

from typing import Literal

from pydantic import BaseModel, Field


class StorySizeSchema(BaseModel):
    story: str = Field(description="The Story label exactly as given, for example S1.")
    rationale: str = Field(
        description="One sentence comparing this Story with the others, or why it cannot be sized."
    )
    points: Literal[1, 2, 3, 5, 8, 13] | None = Field(
        description="The relative size, or null when the Story cannot honestly be sized."
    )


class StoryEstimatesSchema(BaseModel):
    sizes: list[StorySizeSchema] = Field(default_factory=list)
