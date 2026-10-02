"""Semantic INVEST evaluation boundary."""

from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.domain.story.quality import InvestCriterion, ValidationFinding


@dataclass(frozen=True)
class StoryQualityEvidence:
    source_facts: tuple[str, ...] = ()
    human_decisions: tuple[str, ...] = ()
    unconfirmed: tuple[str, ...] = ()
    feature_boundary: tuple[str, ...] = ()

    @classmethod
    def from_context(
        cls, requirement: Requirement, analysis: RequirementAnalysis, feature: Feature
    ) -> "StoryQualityEvidence":
        return cls(
            source_facts=(
                requirement.title.value,
                requirement.description.value,
                *(item.value for item in requirement.business_rules),
                *(item.value for item in requirement.constraints),
                *(f"Declared channel: {item.value}" for item in requirement.channels),
                *(f"Declared system: {item.value}" for item in requirement.systems),
                *((requirement.desired_outcome.value,) if requirement.desired_outcome else ()),
                *((requirement.customer_context.value,) if requirement.customer_context else ()),
                *(item.statement for item in analysis.known_facts),
                *(item.statement for item in analysis.constraints),
                *(item.statement for item in analysis.business_rules),
            ),
            human_decisions=(
                *(f"{item.subject}: {item.answer}" for item in analysis.clarifications),
                *analysis.accepted_constraints,
                *analysis.accepted_business_rules,
                analysis.effective_desired_outcome() or "No confirmed desired outcome supplied.",
            ),
            unconfirmed=(
                *(item.statement for item in analysis.assumptions),
                *(item.question for item in analysis.open_questions),
                *(item.statement for item in analysis.ambiguities),
                *(item.statement for item in analysis.potential_dependencies),
            ),
            feature_boundary=(feature.name.value, feature.outcome.value),
        )


EMPTY_QUALITY_EVIDENCE = StoryQualityEvidence()


class StoryQualityEvaluatorPort(Protocol):
    model: str
    prompt_version: str

    def evaluate(
        self,
        story: UserStory,
        siblings: tuple[UserStory, ...],
        criteria: tuple[InvestCriterion, ...],
        *,
        evidence: StoryQualityEvidence = EMPTY_QUALITY_EVIDENCE,
    ) -> tuple[ValidationFinding, ...]: ...
