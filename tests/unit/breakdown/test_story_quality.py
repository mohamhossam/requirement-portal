"""Slice 6 INVEST validation and SPIDR recommendation tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.errors import StoryQualityEvaluationError
from smb_requirement_agent.breakdown.application.use_cases.story_quality import SuggestStorySplit
from smb_requirement_agent.breakdown.domain.story.errors import InvalidStoryContentError
from smb_requirement_agent.breakdown.domain.story.quality import (
    FindingSource,
    InvestAssessment,
    InvestCriterion,
    SpidrPattern,
    StoryQualityStatus,
    ValidationFinding,
)
from smb_requirement_agent.breakdown.domain.story.value_objects import StoryId
from smb_requirement_agent.breakdown.infrastructure.llm.fake_story_quality_evaluator import (
    FakeStoryQualityEvaluator,
)
from smb_requirement_agent.breakdown.infrastructure.llm.schemas.story_quality_schema import (
    InvestFindingSchema,
    StoryQualitySchema,
)
from smb_requirement_agent.breakdown.infrastructure.llm.story_quality_mapping import (
    request_complete_quality_findings,
    to_quality_findings,
)
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.shared_kernel.generation import Provenance
from tests.conftest import FAKE_PROVIDER_SETTINGS
from tests.unit.workflow_helpers import generate_story_tree

NOW = datetime(2026, 9, 3, tzinfo=UTC)


def _assessment(*failed: InvestCriterion) -> InvestAssessment:
    return InvestAssessment(
        StoryId("story-1"),
        tuple(
            ValidationFinding(
                criterion,
                criterion not in failed,
                f"Evidence for {criterion.value}.",
                FindingSource.SEMANTIC,
            )
            for criterion in InvestCriterion
        ),
        Provenance(NOW, "fake", "quality-v1"),
    )


def test_quality_status_uses_documented_two_failure_split_threshold() -> None:
    assert _assessment().status is StoryQualityStatus.PASSES
    assert _assessment(InvestCriterion.SMALL).status is StoryQualityStatus.NEEDS_ATTENTION
    assert (
        _assessment(InvestCriterion.SMALL, InvestCriterion.ESTIMABLE).status
        is StoryQualityStatus.SPLIT_RECOMMENDED
    )


def test_assessment_requires_exactly_one_finding_per_invest_criterion() -> None:
    with pytest.raises(InvalidStoryContentError, match="every criterion"):
        InvestAssessment(
            StoryId("story-1"),
            _assessment().findings[:-1],
            Provenance(NOW, "fake", "quality-v1"),
        )


def test_split_recommendations_map_failed_criteria_to_spidr() -> None:
    recommendations = SuggestStorySplit.for_assessment(
        _assessment(
            InvestCriterion.INDEPENDENT,
            InvestCriterion.ESTIMABLE,
            InvestCriterion.SMALL,
        )
    )

    assert {item.pattern for item in recommendations} == {
        SpidrPattern.SPIKE,
        SpidrPattern.INTERFACES,
        SpidrPattern.PATHS,
    }


def test_semantic_mapper_rejects_blank_duplicate_or_incomplete_output() -> None:
    requested = (InvestCriterion.INDEPENDENT, InvestCriterion.SMALL)
    with pytest.raises(StoryQualityEvaluationError):
        to_quality_findings(
            StoryQualitySchema(
                findings=[
                    InvestFindingSchema(criterion="independent", passed=True, message="  "),
                    InvestFindingSchema(criterion="small", passed=True, message="bounded"),
                ]
            ),
            requested,
        )
    with pytest.raises(StoryQualityEvaluationError, match="every requested"):
        to_quality_findings(
            StoryQualitySchema(
                findings=[
                    InvestFindingSchema(criterion="independent", passed=True, message="decoupled")
                ]
            ),
            requested,
        )


def test_semantic_mapper_recovers_omitted_criteria_with_focused_requests() -> None:
    requested = (InvestCriterion.INDEPENDENT, InvestCriterion.SMALL)
    calls: list[tuple[InvestCriterion, ...]] = []

    def request_schema(criteria: tuple[InvestCriterion, ...]) -> StoryQualitySchema:
        calls.append(criteria)
        if criteria == requested:
            return StoryQualitySchema(
                findings=[
                    InvestFindingSchema(
                        criterion="independent",
                        passed=True,
                        message="The Story is decoupled from its siblings.",
                    )
                ]
            )
        return StoryQualitySchema(
            findings=[
                InvestFindingSchema(
                    criterion="small",
                    passed=False,
                    message="The Story bundles multiple outcomes.",
                )
            ]
        )

    findings = request_complete_quality_findings(request_schema, requested)

    assert calls == [requested, (InvestCriterion.SMALL,)]
    assert [item.criterion for item in findings] == list(requested)
    assert findings[0].passed is True
    assert findings[1].passed is False


def test_semantic_mapper_rejects_an_incomplete_focused_retry() -> None:
    requested = (InvestCriterion.INDEPENDENT, InvestCriterion.SMALL)

    def request_schema(criteria: tuple[InvestCriterion, ...]) -> StoryQualitySchema:
        if criteria == requested:
            return StoryQualitySchema(
                findings=[
                    InvestFindingSchema(criterion="independent", passed=True, message="Decoupled.")
                ]
            )
        return StoryQualitySchema(findings=[])

    with pytest.raises(StoryQualityEvaluationError, match="every requested"):
        request_complete_quality_findings(request_schema, requested)


def test_story_and_feature_quality_endpoints_are_reviewable(client: TestClient) -> None:
    requirement_id, feature_id, stories = generate_story_tree(client)
    base = f"/requirements/{requirement_id}/features/{feature_id}/stories"

    feature = client.get(f"{base}/quality")
    single = client.get(f"{base}/{stories[0]['id']}/quality")
    recommendations = client.get(f"{base}/{stories[0]['id']}/quality/split-recommendations")

    assert feature.status_code == 200
    assert len(feature.json()["stories"]) == len(stories)
    assert single.status_code == 200
    assert [item["criterion"] for item in single.json()["findings"]] == [
        item.value for item in InvestCriterion
    ]
    assert single.json()["status"] == "passes"
    assert single.json()["provenance"]["model"] == "fake"
    assert recommendations.status_code == 200
    assert recommendations.json() == []


def test_fake_semantic_failures_drive_split_status_and_recommendations() -> None:
    results: dict[InvestCriterion, tuple[bool, str]] = {
        criterion: (True, f"Evidence for {criterion.value}.")
        for criterion in InvestCriterion
        if criterion is not InvestCriterion.TESTABLE
    }
    results[InvestCriterion.ESTIMABLE] = (False, "An integration is unresolved.")
    results[InvestCriterion.SMALL] = (False, "Multiple paths are bundled.")
    container = build_container(
        FAKE_PROVIDER_SETTINGS,
        story_quality_evaluator=FakeStoryQualityEvaluator(results),
    )
    with TestClient(create_app(lambda: container)) as client:
        requirement_id, feature_id, stories = generate_story_tree(client)
        response = client.get(
            f"/requirements/{requirement_id}/features/{feature_id}/stories/"
            f"{stories[0]['id']}/quality"
        )

    assert response.status_code == 200
    assert response.json()["status"] == "split_recommended"
    assert {item["pattern"] for item in response.json()["recommendations"]} == {
        "spike",
        "paths",
    }
