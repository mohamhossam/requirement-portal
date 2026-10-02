"""Structured-output schemas for User Story operations."""

from pydantic import BaseModel, Field


class AcceptanceCriterionSchema(BaseModel):
    given: str = Field(description="Precondition or business context.")
    when: str = Field(description="Action or event under test.")
    then: str = Field(description="Observable expected outcome.")


class StoryItemSchema(BaseModel):
    role: str = Field(description="The user or actor receiving value.")
    action: str = Field(description="What the actor wants to do, without 'I want'.")
    value: str = Field(description="Why the action matters, without 'so that'.")
    acceptance_criteria: list[AcceptanceCriterionSchema] = Field(min_length=1)


class StorySetSchema(BaseModel):
    stories: list[StoryItemSchema] = Field(min_length=1)
