"""LLM schema definition for Epic generation."""

from pydantic import BaseModel, Field


class EpicSchema(BaseModel):
    """Structured output schema for a generated Epic."""

    name: str = Field(description="Short name for the Epic. Not in user-story voice.")
    outcome: str = Field(
        description=(
            "The measurable business outcome the Epic delivers, in the terms the "
            "requirement itself uses."
        )
    )
    business_case: str = Field(
        description="One or two sentences justifying the Epic, grounded in the requirement."
    )
