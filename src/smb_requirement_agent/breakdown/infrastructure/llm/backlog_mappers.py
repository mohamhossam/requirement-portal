"""Map schema-valid Epic, Feature and Story output onto provider-independent candidates.

Structured-output schemas guarantee shape, not usable content. Every backlog generator applies
the same checks here before constructing domain value objects. Split from `candidate_mappers.py`
in ADR-0103 PR 11b.
"""

from __future__ import annotations

from smb_requirement_agent.application.errors import (
    EpicGenerationError,
    FeatureGenerationError,
    StoryGenerationError,
)
from smb_requirement_agent.breakdown.application.ports.epic_generator import EpicCandidate
from smb_requirement_agent.breakdown.application.ports.feature_generator import FeatureCandidate
from smb_requirement_agent.breakdown.application.ports.story_generator import (
    AcceptanceCriterionCandidate,
    StoryCandidate,
)
from smb_requirement_agent.breakdown.infrastructure.llm.schemas.epic_schema import EpicSchema
from smb_requirement_agent.breakdown.infrastructure.llm.schemas.feature_schema import (
    FeatureItemSchema,
    FeatureSetSchema,
)
from smb_requirement_agent.breakdown.infrastructure.llm.schemas.story_schema import StorySetSchema


def to_epic_candidate(parsed: EpicSchema, *, model: str, prompt_version: str) -> EpicCandidate:
    """Reject blank Epic fields and attach generation provenance."""
    name = parsed.name.strip()
    outcome = parsed.outcome.strip()
    business_case = parsed.business_case.strip()

    missing = [
        field
        for field, value in (
            ("name", name),
            ("outcome", outcome),
            ("business_case", business_case),
        )
        if not value
    ]
    if missing:
        raise EpicGenerationError(f"Provider returned blank Epic field(s): {', '.join(missing)}.")

    return EpicCandidate(
        name=name,
        outcome=outcome,
        business_case=business_case,
        model=model,
        prompt_version=prompt_version,
    )


def to_feature_candidates(
    parsed: FeatureSetSchema, *, model: str, prompt_version: str
) -> list[FeatureCandidate]:
    """Drop unusable Feature items and reject an empty decomposition."""
    candidates = [
        candidate
        for item in parsed.features
        if (candidate := _to_feature_candidate(item, model, prompt_version)) is not None
    ]
    if not candidates:
        raise FeatureGenerationError("Provider returned no usable Features for the Epic.")
    return candidates


def _to_feature_candidate(
    item: FeatureItemSchema, model: str, prompt_version: str
) -> FeatureCandidate | None:
    name = item.name.strip()
    outcome = item.outcome.strip()
    rationale = item.splitting_rationale.strip()
    if not (name and outcome and rationale):
        return None
    return FeatureCandidate(
        name=name,
        outcome=outcome,
        delivery_drop=item.delivery_drop,
        splitting_pattern=item.splitting_pattern,
        splitting_rationale=rationale,
        model=model,
        prompt_version=prompt_version,
    )


def to_story_candidates(
    parsed: StorySetSchema, *, model: str, prompt_version: str
) -> list[StoryCandidate]:
    """Map an all-or-nothing Story response after strict content validation."""
    if not parsed.stories:
        raise StoryGenerationError("Provider returned no Stories for the Feature.")
    candidates: list[StoryCandidate] = []
    for index, item in enumerate(parsed.stories, start=1):
        role, action, value = item.role.strip(), item.action.strip(), item.value.strip()
        if not (role and action and value):
            raise StoryGenerationError(f"Provider returned blank content in Story {index}.")
        if not item.acceptance_criteria:
            raise StoryGenerationError(
                f"Provider returned no acceptance criteria for Story {index}."
            )
        criteria: list[AcceptanceCriterionCandidate] = []
        for criterion_index, criterion in enumerate(item.acceptance_criteria, start=1):
            given = criterion.given.strip()
            when = criterion.when.strip()
            then = criterion.then.strip()
            if not (given and when and then):
                raise StoryGenerationError(
                    "Provider returned an incomplete acceptance criterion in "
                    f"Story {index}, criterion {criterion_index}."
                )
            criteria.append(AcceptanceCriterionCandidate(given=given, when=when, then=then))
        candidates.append(
            StoryCandidate(
                role=role,
                action=action,
                value=value,
                acceptance_criteria=criteria,
                model=model,
                prompt_version=prompt_version,
            )
        )
    return candidates
