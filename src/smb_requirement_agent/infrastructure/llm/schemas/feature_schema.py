"""LLM schema definitions for Feature decomposition."""

from typing import Literal

from pydantic import BaseModel, Field


class FeatureItemSchema(BaseModel):
    """One Feature in the decomposition."""

    name: str = Field(description="Short name for the Feature. Not in user-story voice.")
    outcome: str = Field(
        description="The one measurable outcome this Feature delivers, as capability plus benefit."
    )
    delivery_drop: Literal["mvp", "later"] = Field(
        description="Whether this is core MVP scope or a later drop."
    )
    splitting_pattern: Literal[
        "component_system",
        "journey_stage",
        "mvp_vs_later",
        "channel",
        "business_variant",
    ] = Field(description="Which splitting strategy produced this Feature.")
    splitting_rationale: str = Field(
        description="Why this is a separate Feature rather than part of another."
    )


class FeatureSetSchema(BaseModel):
    """Structured output schema for a Feature decomposition."""

    features: list[FeatureItemSchema] = Field(
        description="The Features this Epic splits into. Never empty.",
        default_factory=list,
    )
