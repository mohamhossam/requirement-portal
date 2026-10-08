"""Validate and complete semantic INVEST output before constructing findings."""

from collections.abc import Callable

from smb_requirement_agent.application.errors import StoryQualityEvaluationError
from smb_requirement_agent.breakdown.domain.story.quality import (
    FindingSource,
    InvestCriterion,
    ValidationFinding,
)
from smb_requirement_agent.breakdown.infrastructure.llm.schemas.story_quality_schema import (
    StoryQualitySchema,
)

QualitySchemaRequest = Callable[[tuple[InvestCriterion, ...]], StoryQualitySchema]


def _map_available_findings(
    schema: StoryQualitySchema, requested: tuple[InvestCriterion, ...]
) -> dict[InvestCriterion, ValidationFinding]:
    by_criterion: dict[InvestCriterion, ValidationFinding] = {}
    for item in schema.findings:
        criterion = InvestCriterion(item.criterion)
        message = item.message.strip()
        if criterion not in requested or criterion in by_criterion or not message:
            raise StoryQualityEvaluationError(
                "Quality evaluator returned duplicate, unexpected, or blank findings."
            )
        by_criterion[criterion] = ValidationFinding(
            criterion, item.passed, message, FindingSource.SEMANTIC
        )
    return by_criterion


def to_quality_findings(
    schema: StoryQualitySchema, requested: tuple[InvestCriterion, ...]
) -> tuple[ValidationFinding, ...]:
    by_criterion = _map_available_findings(schema, requested)
    if set(by_criterion) != set(requested):
        raise StoryQualityEvaluationError(
            "Quality evaluator did not return every requested INVEST criterion."
        )
    return tuple(by_criterion[item] for item in requested)


def request_complete_quality_findings(
    request_schema: QualitySchemaRequest,
    requested: tuple[InvestCriterion, ...],
) -> tuple[ValidationFinding, ...]:
    """Recover omitted findings with one bounded, focused request per criterion."""
    if not requested:
        return ()

    by_criterion = _map_available_findings(request_schema(requested), requested)
    missing = tuple(item for item in requested if item not in by_criterion)
    for criterion in missing:
        focused = to_quality_findings(request_schema((criterion,)), (criterion,))
        by_criterion[criterion] = focused[0]

    return tuple(by_criterion[item] for item in requested)
