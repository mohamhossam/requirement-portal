"""Generation checks are part of the atomic draft operation, not a browser follow-up."""

from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.analysis.domain.value_objects import KnownFact
from smb_requirement_agent.breakdown.application.errors import (
    StoryGenerationError,
    StoryQualityEvaluationError,
)
from smb_requirement_agent.breakdown.application.ports.feature_generator import FeatureCandidate
from smb_requirement_agent.breakdown.application.ports.generation_guidance import (
    EMPTY_GENERATION_GUIDANCE,
    GenerationGuidance,
)
from smb_requirement_agent.breakdown.application.ports.story_generator import StoryCandidate
from smb_requirement_agent.breakdown.application.ports.story_quality_evaluator import (
    EMPTY_QUALITY_EVIDENCE,
)
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.breakdown.domain.feature.entities import Feature
from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.breakdown.domain.story.quality import (
    FindingSource,
    InvestCriterion,
    StoryQualityEvidence,
    ValidationFinding,
)
from smb_requirement_agent.breakdown.domain.story.value_objects import BusinessValue
from smb_requirement_agent.breakdown.infrastructure.backlog_payloads import (
    story_proposal_from_payload,
    story_proposal_to_payload,
)
from smb_requirement_agent.breakdown.infrastructure.llm.fake_feature_generator import (
    FakeFeatureGenerator,
)
from smb_requirement_agent.breakdown.infrastructure.llm.fake_story_generator import (
    FakeStoryGenerator,
)
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.references.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureQuery,
)
from smb_requirement_agent.references.domain.architecture.catalogue import (
    ArchitectureDependency,
    SystemReference,
)
from smb_requirement_agent.references.infrastructure.knowledge_client import OFFLINE_RELEASE_ID
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.unit.workflow_helpers import generate_story_tree


def candidate(action: str) -> StoryCandidate:
    return StoryCandidate(
        role="customer",
        action=action,
        value="receive the supported capability",
        acceptance_criteria=[
            {
                "given": "the approved requirement applies",
                "when": action,
                "then": "the supported outcome is observable",
            }
        ],
        model="scripted",
        prompt_version="scripted-v1",
    )


class RefiningGenerator(FakeStoryGenerator):
    def __init__(self) -> None:
        super().__init__()
        self.guidance: list[GenerationGuidance] = []
        self.refine = True
        self.fail_refinement = False

    def generate(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        feature: Feature,
        *,
        guidance: GenerationGuidance = EMPTY_GENERATION_GUIDANCE,
    ) -> list[StoryCandidate]:
        self._check()
        self.guidance.append(guidance)
        if guidance.feedback and self.fail_refinement:
            raise StoryGenerationError("Refinement provider failed")
        if guidance.feedback and self.refine:
            return [
                candidate("complete the happy path"),
                candidate("enforce required security"),
                candidate("handle the supported error path and performance constraint"),
            ]
        return [candidate("combined happy path, required security, error path and performance")]


class ContentEvaluator:
    model = "content-evaluator"
    prompt_version = "test-v1"

    def __init__(self) -> None:
        self.calls = 0
        self.fail = False
        self.always_fail = False
        self.failed_criteria = {InvestCriterion.SMALL, InvestCriterion.INDEPENDENT}
        self.evidence: list[StoryQualityEvidence] = []
        self.hook: Callable[[], None] = lambda: None

    def evaluate(
        self,
        story: UserStory,
        siblings: tuple[UserStory, ...],
        criteria: tuple[InvestCriterion, ...],
        *,
        evidence: StoryQualityEvidence = EMPTY_QUALITY_EVIDENCE,
    ) -> tuple[ValidationFinding, ...]:
        self.calls += 1
        self.evidence.append(evidence)
        self.hook()
        if self.fail:
            raise StoryQualityEvaluationError("Unusable quality response")
        return tuple(
            ValidationFinding(
                criterion,
                not (
                    ("combined" in story.action.value or self.always_fail)
                    and criterion in self.failed_criteria
                ),
                "Split the combined outcomes"
                if "combined" in story.action.value
                else "Specific outcome",
                FindingSource.SEMANTIC,
            )
            for criterion in criteria
        )


def regenerate(client: TestClient, path: str) -> Any:
    context = client.get(path).json()["generation_context_token"]
    return client.post(f"{path}/regeneration", json={"context_token": context, "force": True})


def test_refines_before_save_and_reads_reuse_exact_final_assessment() -> None:
    generator, evaluator = RefiningGenerator(), ContentEvaluator()
    container = build_container(
        Settings(llm_provider=LLMProvider.FAKE),
        story_generator=generator,
        story_quality_evaluator=evaluator,
    )
    with TestClient(create_app(lambda: container)) as client:
        requirement_id, feature_id, stories = generate_story_tree(client)
        assert len(generator.guidance) == 2
        assert generator.guidance[0].architecture is not None
        correction = generator.guidance[1]
        assert any("small" in item for item in correction.feedback)
        assert correction.minimum_story_count == 2
        assert evaluator.evidence[0].source_facts
        assert evaluator.evidence[0].feature_boundary
        assert all(item == evaluator.evidence[0] for item in evaluator.evidence)
        assert "security" in correction.previous_draft[0]
        assert len(stories) == 3
        assert all(story["architecture"] is not None for story in stories)
        assert all(term in str(stories) for term in ("security", "error path", "performance"))
        calls = evaluator.calls
        assert calls == 4  # initial broad Story plus the three final Stories
        quality = client.get(
            f"/requirements/{requirement_id}/features/{feature_id}/stories/quality-assessment"
        ).json()
        assert quality["fresh"]
        assert {item["story_id"] for item in quality["stories"]} == {s["id"] for s in stories}
        assert all(
            len(item["findings"]) == 6 and item["failure_count"] == 0 for item in quality["stories"]
        )
        review_path = f"/requirements/{requirement_id}/breakdown-review"
        assert client.get(review_path).json()["fresh"]
        assert client.post(review_path).status_code == 200
        assert evaluator.calls == calls


def test_quality_cache_changes_with_business_evidence_without_provider_calls_on_read() -> None:
    evaluator = ContentEvaluator()
    container = build_container(
        Settings(llm_provider=LLMProvider.FAKE), story_quality_evaluator=evaluator
    )
    with TestClient(create_app(lambda: container)) as client:
        requirement_id, feature_id, _ = generate_story_tree(client)
        path = f"/requirements/{requirement_id}/features/{feature_id}/stories"
        snapshot = client.get(path + "/quality-assessment").json()
        analysis = container.analysis_repository.get_by_requirement_id(
            RequirementId(requirement_id)
        )
        assert analysis is not None
        container.analysis_repository.save(
            replace(
                analysis,
                known_facts=(*analysis.known_facts, KnownFact("Manual approval is required.")),
                version=analysis.version + 1,
            )
        )
        calls = evaluator.calls
        current = client.get(path + "/quality-assessment").json()
        assert not current["fresh"]
        assert current["stories"] == snapshot["stories"]
        assert evaluator.calls == calls
        review = client.post(f"/requirements/{requirement_id}/breakdown-review")
        assert review.status_code == 200
        refreshed = client.get(path + "/quality-assessment").json()
        assert refreshed["fresh"]
        assert refreshed["source_fingerprint"] != snapshot["source_fingerprint"]
        assert "Manual approval is required." in evaluator.evidence[-1].source_facts


def test_unresolved_quality_is_saved_after_only_one_correction() -> None:
    generator, evaluator = RefiningGenerator(), ContentEvaluator()
    generator.refine = False
    # Missing decisions and real dependencies can remain without a size violation.
    evaluator.failed_criteria = {InvestCriterion.ESTIMABLE, InvestCriterion.INDEPENDENT}
    container = build_container(
        Settings(llm_provider=LLMProvider.FAKE),
        story_generator=generator,
        story_quality_evaluator=evaluator,
    )
    with TestClient(create_app(lambda: container)) as client:
        requirement_id, _, stories = generate_story_tree(client)
        assert len(stories) == 1
        assert len(generator.guidance) == 2
        assert evaluator.calls == 2
        review = client.get(f"/requirements/{requirement_id}/breakdown-review").json()
        assert any(
            flag["category"] == "quality" and flag["severity"] == "blocking"
            for flag in review["flags"]
        )
        assert review["quality_assessments"][0]["failure_count"] == 2


@pytest.mark.parametrize(
    "failure", ["generator", "refinement", "ignored_split", "evaluator", "save"]
)
def test_failed_generation_preserves_content_quality_and_review(
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator, evaluator = RefiningGenerator(), ContentEvaluator()
    container = build_container(
        Settings(llm_provider=LLMProvider.FAKE),
        story_generator=generator,
        story_quality_evaluator=evaluator,
    )
    with TestClient(create_app(lambda: container)) as client:
        requirement_id, feature_id, _ = generate_story_tree(client)
        path = f"/requirements/{requirement_id}/features/{feature_id}/stories"
        before = client.get(path).json()
        review_path = f"/requirements/{requirement_id}/breakdown-review"
        review = client.get(review_path).json()
        snapshot = container.story_quality_repository.get(FeatureId(feature_id))
        if failure == "generator":
            generator.should_fail = True
        elif failure == "refinement":
            generator.fail_refinement = True
        elif failure == "ignored_split":
            generator.refine = False
        elif failure == "evaluator":
            evaluator.fail = True
        else:
            save = container.story_quality_repository.save

            def fail_save(value: Any) -> None:
                save(value)
                raise RuntimeError("Injected commit failure")

            monkeypatch.setattr(container.story_quality_repository, "save", fail_save)
        if failure == "save":
            with pytest.raises(RuntimeError, match="Injected commit failure"):
                regenerate(client, path)
        else:
            assert regenerate(client, path).status_code == 502
        assert client.get(path).json() == before
        assert client.get(review_path).json() == review
        assert container.story_quality_repository.get(FeatureId(feature_id)) == snapshot


def test_checked_preview_survives_serialization_and_apply_without_new_evaluation() -> None:
    evaluator = ContentEvaluator()
    container = build_container(
        Settings(llm_provider=LLMProvider.FAKE), story_quality_evaluator=evaluator
    )
    with TestClient(create_app(lambda: container)) as client:
        requirement_id, feature_id, stories = generate_story_tree(client)
        path = f"/requirements/{requirement_id}/features/{feature_id}/stories"
        context = client.get(path).json()["generation_context_token"]
        created = client.post(
            f"{path}/change-proposals",
            json={
                "operation": "split",
                "source_story_ids": [stories[0]["id"]],
                "context_token": context,
            },
        )
        assert created.status_code == 201, created.text
        assert all(item["quality"] is not None for item in created.json()["candidates"])
        stored = container.story_proposal_repository.list_for_feature(FeatureId(feature_id))[0]
        restored = story_proposal_from_payload(story_proposal_to_payload(stored))
        assert restored == stored
        container.story_proposal_repository.save(restored)
        calls = evaluator.calls
        applied = client.post(
            f"{path}/change-proposals/{stored.id.value}/application",
            json={
                "expected_version": stored.version,
                "expected_set_version": client.get(path).json()["set_version"],
            },
        )
        assert applied.status_code == 200, applied.text
        retained = next(
            item for item in applied.json()["stories"] if item["id"] == stories[0]["id"]
        )
        assert retained["version"] > stories[0]["version"]
        assert evaluator.calls == calls
        assert client.get(f"{path}/quality-assessment").json()["fresh"]
        assert client.get(f"/requirements/{requirement_id}/breakdown-review").json()["fresh"]


class CrossSystemFeatures(FakeFeatureGenerator):
    def __init__(self) -> None:
        super().__init__()
        self.guidance: list[GenerationGuidance] = []

    def generate(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        *,
        guidance: GenerationGuidance = EMPTY_GENERATION_GUIDANCE,
    ) -> list[FeatureCandidate]:
        self.guidance.append(guidance)
        result = super().generate(requirement, analysis, epic, guidance=guidance)
        result[0]["name"] = "BCRM and BSCS coordination"
        return result


class NamedSystems:
    """The knowledge service's matching for these tests: BCRM and BSCS, by name in the text.

    BCRM orders through BSCS, so a Feature naming both crosses systems.
    """

    def match(self, query: ArchitectureQuery) -> ArchitectureKnowledgeMatch:
        text = " ".join(query.text)
        systems = tuple(
            SystemReference(name.lower(), name, True) for name in ("BCRM", "BSCS") if name in text
        )
        dependencies = (
            (ArchitectureDependency("bcrm", "bscs", "BCRM orders through BSCS."),)
            if len(systems) == 2
            else ()
        )
        return ArchitectureKnowledgeMatch(OFFLINE_RELEASE_ID, systems, dependencies)


def test_feature_generation_considers_catalogue_and_keeps_unavoidable_dependency() -> None:
    generator = CrossSystemFeatures()
    container = build_container(
        Settings(llm_provider=LLMProvider.FAKE),
        feature_generator=generator,
        architecture_knowledge=NamedSystems(),
    )
    with TestClient(create_app(lambda: container)) as client:
        requirement_id, _, _ = generate_story_tree(client)
        assert len(generator.guidance) == 2
        assert generator.guidance[1].feedback
        assert "BCRM" in generator.guidance[1].previous_draft[0]
        features = client.get(f"/requirements/{requirement_id}/features").json()["features"]
        assert features[0]["architecture"]["cross_system"]
        review = client.get(f"/requirements/{requirement_id}/breakdown-review").json()
        assert any(flag["title"] == "Cross-system Feature" for flag in review["flags"])


def test_generation_rejects_concurrent_story_edit_without_overwriting_it() -> None:
    evaluator = ContentEvaluator()
    container = build_container(
        Settings(llm_provider=LLMProvider.FAKE), story_quality_evaluator=evaluator
    )
    with TestClient(create_app(lambda: container)) as client:
        requirement_id, feature_id, _ = generate_story_tree(client)
        feature = FeatureId(feature_id)
        original = container.story_repository.get_by_feature_id(feature)[0]
        edited = original.edit(
            original.role,
            original.action,
            BusinessValue("Concurrent human value"),
            original.acceptance_criteria,
        )

        def concurrent_edit() -> None:
            evaluator.hook = lambda: None
            container.story_repository.save(edited)

        evaluator.hook = concurrent_edit
        snapshot = container.story_quality_repository.get(feature)
        path = f"/requirements/{requirement_id}/features/{feature_id}/stories"
        assert regenerate(client, path).status_code == 409
        assert container.story_repository.get(feature, original.id) == edited
        assert container.story_quality_repository.get(feature) == snapshot


def test_preview_rejects_changed_parent_evidence_and_legacy_payload_remains_readable() -> None:
    container = build_container(Settings(llm_provider=LLMProvider.FAKE))
    with TestClient(create_app(lambda: container)) as client:
        requirement_id, feature_id, stories = generate_story_tree(client)
        path = f"/requirements/{requirement_id}/features/{feature_id}/stories"
        response = client.post(
            f"{path}/change-proposals",
            json={
                "operation": "merge",
                "source_story_ids": [item["id"] for item in stories],
                "context_token": client.get(path).json()["generation_context_token"],
            },
        )
        assert response.status_code == 201, response.text
        assert len(response.json()["candidates"]) == 1
        stored = container.story_proposal_repository.list_for_feature(FeatureId(feature_id))[0]
        payload = story_proposal_to_payload(stored)
        for key in (
            "prepared_candidates",
            "quality_assessments",
            "generation_context",
            "source_set_fingerprint",
        ):
            payload.pop(key)
        legacy = story_proposal_from_payload(payload)
        assert not legacy.prepared_candidates and not legacy.quality_assessments
        analysis = container.analysis_repository.get_by_requirement_id(
            RequirementId(requirement_id)
        )
        assert analysis is not None
        container.analysis_repository.save(replace(analysis, version=analysis.version + 1))
        applied = client.post(
            f"{path}/change-proposals/{stored.id.value}/application",
            json={
                "expected_version": stored.version,
                "expected_set_version": client.get(path).json()["set_version"],
            },
        )
        assert applied.status_code == 409
        assert len(client.get(path).json()["stories"]) == len(stories)
