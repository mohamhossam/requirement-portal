"""Tests for the Feature use cases and the three-level invalidation cascade."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.analysis.application.use_cases.analysis_collaboration import (
    AnalysisCollaboration,
)
from smb_requirement_agent.analysis.application.use_cases.analyze_requirement import (
    AnalyzeRequirement,
)
from smb_requirement_agent.analysis.application.use_cases.confirm_requirement_analysis import (
    ConfirmRequirementAnalysis,
)
from smb_requirement_agent.analysis.infrastructure.in_memory_analysis_audit_repository import (
    InMemoryAnalysisAuditRepository,
)
from smb_requirement_agent.analysis.infrastructure.in_memory_analysis_repository import (
    InMemoryRequirementAnalysisRepository,
)
from smb_requirement_agent.analysis.infrastructure.llm.fake_requirement_analyzer import (
    FakeRequirementAnalyzer,
)
from smb_requirement_agent.application.errors import (
    EpicNotFoundError,
    FeatureNotFoundError,
    FeaturesNotFoundError,
    RequirementAnalysisNotFoundError,
)
from smb_requirement_agent.application.use_cases.approval_workflow import ApprovalRecorder
from smb_requirement_agent.application.use_cases.approve_epic import ApproveEpic
from smb_requirement_agent.application.use_cases.approve_feature import ApproveFeature
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.breakdown.application.ports.generation_guidance import (
    EMPTY_GENERATION_GUIDANCE,
)
from smb_requirement_agent.breakdown.application.use_cases.edit_epic import EditEpic, EditEpicInput
from smb_requirement_agent.breakdown.application.use_cases.feature_review import (
    EditFeature,
    EditFeatureInput,
    GetFeatures,
)
from smb_requirement_agent.breakdown.application.use_cases.generate_epic import GenerateEpic
from smb_requirement_agent.breakdown.application.use_cases.generate_features import GenerateFeatures
from smb_requirement_agent.breakdown.application.use_cases.generation_checks import GenerationChecks
from smb_requirement_agent.breakdown.domain.epic.errors import EpicNotApprovedError
from smb_requirement_agent.breakdown.domain.epic.value_objects import EpicId
from smb_requirement_agent.breakdown.domain.feature.entities import Feature
from smb_requirement_agent.breakdown.domain.feature.errors import (
    FeatureRegenerationConflictError,
    InvalidFeatureContentError,
    StaleFeatureApprovalError,
)
from smb_requirement_agent.breakdown.domain.feature.value_objects import (
    DeliveryDrop,
    FeatureId,
    FeatureStatus,
    SplittingPattern,
)
from smb_requirement_agent.breakdown.infrastructure.in_memory_epic_repository import (
    InMemoryEpicRepository,
)
from smb_requirement_agent.breakdown.infrastructure.in_memory_feature_repository import (
    InMemoryFeatureRepository,
)
from smb_requirement_agent.breakdown.infrastructure.in_memory_story_repository import (
    InMemoryStoryChangeProposalRepository,
    InMemoryStoryRepository,
)
from smb_requirement_agent.breakdown.infrastructure.llm.fake_epic_generator import FakeEpicGenerator
from smb_requirement_agent.breakdown.infrastructure.llm.fake_feature_generator import (
    FakeFeatureGenerator,
)
from smb_requirement_agent.domain.review.fingerprints import artifact_fingerprint
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.identity.infrastructure.in_memory_identity import (
    InMemoryAccessRepository,
    InMemoryActorDirectory,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_breakdown_review_repository import (
    InMemoryBreakdownReviewRepository,
)
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirementInput,
)
from smb_requirement_agent.requirements.application.use_cases.update_requirement import (
    UpdateRequirement,
    UpdateRequirementInput,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.infrastructure.in_memory_document_repository import (
    InMemoryDocumentRepository,
)
from smb_requirement_agent.requirements.infrastructure.in_memory_requirement_repository import (
    InMemoryRequirementRepository,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.staleness import StaleReason
from tests.conftest import (
    AcceptAllSuggestionValidator,
    AlwaysReadyKnowledgeReview,
    NoOpAnswerSuggestionScheduler,
    NoOpKnowledgeScheduler,
    make_analysis_documents,
    make_event_publisher,
)
from tests.reference_helpers import EmptyReferences
from tests.unit.access_service import access_service_for
from tests.unit.owned_requirement_creator import OwnedRequirementCreator
from tests.unit.transaction_stub import NoOpTransactionManager

GENERATED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = GENERATED_AT + timedelta(hours=3)

EDIT = EditFeatureInput(
    name="Human name",
    outcome="Human outcome",
    delivery_drop="later",
    splitting_pattern="channel",
    splitting_rationale="Human rationale",
)


class World:
    """A fully wired in-memory world for one test."""

    def __init__(self) -> None:
        self.requirements = InMemoryRequirementRepository()
        self.analyses = InMemoryRequirementAnalysisRepository()
        self.epics = InMemoryEpicRepository()
        self.features = InMemoryFeatureRepository()
        self.stories = InMemoryStoryRepository()
        self.proposals = InMemoryStoryChangeProposalRepository()
        self.access = InMemoryAccessRepository()
        self.generator = FakeFeatureGenerator()
        self.clock = FixedClock(GENERATED_AT)
        self.audits = InMemoryAnalysisAuditRepository(lambda requirement_id: None)
        self.reviews = InMemoryBreakdownReviewRepository()

        self.events = make_event_publisher(
            self.analyses,
            self.epics,
            self.features,
            self.stories,
            self.clock,
            self.audits,
            reviews=self.reviews,
        )
        self.contexts = GenerationContextTokens(
            self.requirements,
            self.analyses,
            self.audits,
            InMemoryDocumentRepository(),
            self.epics,
            self.features,
            self.stories,
            self.proposals,
            transactions=NoOpTransactionManager(),
            references=EmptyReferences(),
        )
        self.create = OwnedRequirementCreator(
            self.requirements, self.access, FAKE_ACTORS[0], self.clock
        )
        self.analyze = AnalyzeRequirement(
            AnalysisCollaboration(
                self.requirements,
                self.analyses,
                self.audits,
                FakeRequirementAnalyzer(),
                make_analysis_documents(),
                self.access,
                InMemoryActorDirectory(FAKE_ACTORS),
                self.clock,
                NoOpTransactionManager(),
                NoOpKnowledgeScheduler(),
                NoOpAnswerSuggestionScheduler(),
                AcceptAllSuggestionValidator(),
                contexts=self.contexts,
                references=EmptyReferences(),
                reference_grounding=EmptyReferences(),
                authorization=access_service_for(self.requirements, self.access),
            )
        )
        self.generate_epic = GenerateEpic(
            self.requirements,
            self.analyses,
            self.epics,
            FakeEpicGenerator(),
            self.clock,
            self.events,
            NoOpTransactionManager(),
            authorization=access_service_for(self.requirements, self.access),
            contexts=self.contexts,
        )
        self.confirm_analysis = ConfirmRequirementAnalysis(
            self.requirements,
            self.analyses,
            self.clock,
            access_service_for(self.requirements, self.access),
            self.audits,
            AlwaysReadyKnowledgeReview(),
            NoOpTransactionManager(),
            EmptyReferences(),
        )
        self.edit_epic = EditEpic(
            self.requirements,
            self.epics,
            self.events,
            NoOpTransactionManager(),
            authorization=access_service_for(self.requirements, self.access),
        )
        recorder = ApprovalRecorder(
            self.access, self.clock, access_service_for(self.requirements, self.access)
        )
        self.approve_epic = ApproveEpic(
            self.requirements, self.epics, recorder, NoOpTransactionManager()
        )
        checks = Mock(spec=GenerationChecks)
        checks.features.side_effect = lambda requirement, analysis, generate: generate(
            EMPTY_GENERATION_GUIDANCE
        )
        self.generate = GenerateFeatures(
            self.requirements,
            self.analyses,
            self.epics,
            self.features,
            self.stories,
            self.proposals,
            self.generator,
            self.clock,
            self.events,
            NoOpTransactionManager(),
            authorization=access_service_for(self.requirements, self.access),
            contexts=self.contexts,
            checks=checks,
        )
        self.get = GetFeatures(self.requirements, self.epics, self.features)
        self.edit = EditFeature(
            self.requirements,
            self.epics,
            self.features,
            self.events,
            NoOpTransactionManager(),
            authorization=access_service_for(self.requirements, self.access),
        )
        self.approve = ApproveFeature(
            self.requirements,
            self.epics,
            self.features,
            recorder,
            NoOpTransactionManager(),
        )
        self.update = UpdateRequirement(
            self.requirements,
            self.events,
            self.clock,
            NoOpTransactionManager(),
            authorization=access_service_for(self.requirements, self.access),
            documents=InMemoryDocumentRepository(),
        )

    def confirmed_analysis_requirement(self) -> Requirement:
        requirement = self.create.execute(
            CreateRequirementInput(
                title="Bundle ordering",
                description="Order in channel",
                desired_outcome="Customers can complete an order in channel.",
            )
        )
        analysis = self.analyze.execute(FAKE_ACTORS[0], requirement.id)
        self.analyses.save(
            replace(
                analysis,
                version=analysis.version + 1,
                assumptions=(),
                open_questions=(),
                ambiguities=(),
                potential_dependencies=(),
            )
        )
        for question in self.audits.list_questions(requirement.id):
            self.audits.save_question(question.supersede())
        current_analysis = self.analyses.get_by_requirement_id(requirement.id)
        assert current_analysis is not None
        self.confirm_analysis.execute(requirement.id, FAKE_ACTORS[0], current_analysis.version)
        return requirement

    def approved_epic_requirement(self) -> Requirement:
        requirement = self.confirmed_analysis_requirement()
        self.generate_epic.execute(FAKE_ACTORS[0], requirement.id)
        epic = self.epics.get_by_requirement_id(requirement.id)
        assert epic is not None
        self.approve_epic.execute(
            requirement.id,
            FAKE_ACTORS[0],
            epic.version,
            artifact_fingerprint(epic),
        )
        return requirement

    def approve_current(self, requirement_id: RequirementId, feature_id: FeatureId) -> Feature:
        feature = next(item for item in self.get.execute(requirement_id) if item.id == feature_id)
        return self.approve.execute(
            requirement_id,
            feature_id,
            FAKE_ACTORS[0],
            feature.version,
            artifact_fingerprint(feature),
        )

    def decomposed(self) -> Requirement:
        requirement = self.approved_epic_requirement()
        self.generate.execute(FAKE_ACTORS[0], requirement.id)
        return requirement


@pytest.fixture
def world() -> World:
    return World()


class TestGenerateFeatures:
    def test_decomposes_an_approved_epic(self, world: World) -> None:
        requirement = world.approved_epic_requirement()

        result = world.generate.execute(FAKE_ACTORS[0], requirement.id)

        assert result.replaced_existing is False
        assert len(result.features) == 2
        assert all(f.status is FeatureStatus.GENERATED for f in result.features)

    def test_every_feature_traces_to_the_epic(self, world: World) -> None:
        requirement = world.approved_epic_requirement()
        epic = world.epics.get_by_requirement_id(requirement.id)
        assert epic is not None

        features = world.generate.execute(FAKE_ACTORS[0], requirement.id).features

        assert {f.epic_id for f in features} == {epic.id}

    def test_candidate_strings_map_onto_domain_enums(self, world: World) -> None:
        requirement = world.approved_epic_requirement()

        first, second = world.generate.execute(FAKE_ACTORS[0], requirement.id).features

        assert first.delivery_drop is DeliveryDrop.MVP
        assert first.splitting_pattern is SplittingPattern.JOURNEY_STAGE
        assert second.delivery_drop is DeliveryDrop.LATER
        assert second.splitting_pattern is SplittingPattern.COMPONENT_SYSTEM

    def test_provenance_is_stamped_from_the_clock(self, world: World) -> None:
        requirement = world.approved_epic_requirement()

        features = world.generate.execute(FAKE_ACTORS[0], requirement.id).features

        assert all(f.provenance.generated_at == GENERATED_AT for f in features)

    def test_unapproved_epic_cannot_be_decomposed(self, world: World) -> None:
        """Decomposing a draft Epic builds a backlog on unsigned-off text."""
        requirement = world.confirmed_analysis_requirement()
        world.generate_epic.execute(FAKE_ACTORS[0], requirement.id)

        with pytest.raises(EpicNotApprovedError):
            world.generate.execute(FAKE_ACTORS[0], requirement.id)

    def test_stale_epic_cannot_be_decomposed(self, world: World) -> None:
        """Re-analysing after a change is not enough; the Epic must be reconciled.

        The analysis is re-run first because a requirement change deletes it,
        which would otherwise mask the staleness check behind a 404.
        """
        requirement = world.approved_epic_requirement()
        world.update.execute(
            FAKE_ACTORS[0],
            requirement.id,
            UpdateRequirementInput(title="Changed", description="Changed", expected_version=1),
        )
        world.analyze.execute(FAKE_ACTORS[0], requirement.id)

        with pytest.raises(EpicNotApprovedError, match="stale"):
            world.generate.execute(FAKE_ACTORS[0], requirement.id)

    def test_a_changed_requirement_asks_for_re_analysis_first(self, world: World) -> None:
        """Both the analysis and the Epic are invalid, and re-analysis comes first."""
        requirement = world.approved_epic_requirement()
        world.update.execute(
            FAKE_ACTORS[0],
            requirement.id,
            UpdateRequirementInput(title="Changed", description="Changed", expected_version=1),
        )

        with pytest.raises(RequirementAnalysisNotFoundError):
            world.generate.execute(FAKE_ACTORS[0], requirement.id)

    def test_missing_epic_raises(self, world: World) -> None:
        requirement = world.create.execute(CreateRequirementInput(title="T", description="D"))
        world.analyze.execute(FAKE_ACTORS[0], requirement.id)

        with pytest.raises(EpicNotFoundError):
            world.generate.execute(FAKE_ACTORS[0], requirement.id)

    def test_regenerating_untouched_features_is_allowed(self, world: World) -> None:
        requirement = world.decomposed()

        assert world.generate.execute(FAKE_ACTORS[0], requirement.id).replaced_existing is True

    @pytest.mark.parametrize("action", ["edit", "approve"])
    def test_regenerating_human_owned_features_is_refused(self, world: World, action: str) -> None:
        requirement = world.decomposed()
        first = world.get.execute(requirement.id)[0]
        if action == "edit":
            world.edit.execute(FAKE_ACTORS[0], requirement.id, first.id, EDIT)
        else:
            world.approve_current(requirement.id, first.id)

        with pytest.raises(FeatureRegenerationConflictError):
            world.generate.execute(FAKE_ACTORS[0], requirement.id)

    def test_force_replaces_the_whole_set(self, world: World) -> None:
        requirement = world.decomposed()
        first = world.get.execute(requirement.id)[0]
        world.approve_current(requirement.id, first.id)

        result = world.generate.execute(FAKE_ACTORS[0], requirement.id, force=True)

        assert all(f.status is FeatureStatus.GENERATED for f in result.features)


class TestFeatureReview:
    def test_get_without_features_raises(self, world: World) -> None:
        requirement = world.approved_epic_requirement()

        with pytest.raises(FeaturesNotFoundError):
            world.get.execute(requirement.id)

    def test_editing_one_feature_leaves_its_siblings_untouched(self, world: World) -> None:
        """The test that collection state is genuinely per-item."""
        requirement = world.decomposed()
        first, second = world.get.execute(requirement.id)

        world.edit.execute(FAKE_ACTORS[0], requirement.id, first.id, EDIT)

        after_first, after_second = world.get.execute(requirement.id)
        assert after_first.status is FeatureStatus.EDITED
        assert after_first.name.value == "Human name"
        assert after_second.status is FeatureStatus.GENERATED
        assert after_second.name == second.name

    def test_approving_one_feature_leaves_its_siblings_untouched(self, world: World) -> None:
        requirement = world.decomposed()
        first = world.get.execute(requirement.id)[0]

        world.approve_current(requirement.id, first.id)

        after_first, after_second = world.get.execute(requirement.id)
        assert after_first.status is FeatureStatus.APPROVED
        assert after_second.status is FeatureStatus.GENERATED

    def test_a_feature_id_from_another_epic_is_rejected(self, world: World) -> None:
        requirement = world.decomposed()

        with pytest.raises(FeatureNotFoundError):
            world.edit.execute(
                FAKE_ACTORS[0], requirement.id, FeatureId("someone-elses-feature"), EDIT
            )

    def test_unsupported_enum_value_from_a_caller_is_a_content_error(self, world: World) -> None:
        requirement = world.decomposed()
        first = world.get.execute(requirement.id)[0]

        with pytest.raises(InvalidFeatureContentError, match="splitting pattern"):
            world.edit.execute(
                FAKE_ACTORS[0],
                requirement.id,
                first.id,
                EditFeatureInput(
                    name="n",
                    outcome="o",
                    delivery_drop="mvp",
                    splitting_pattern="astrology",
                    splitting_rationale="r",
                ),
            )


class TestCascade:
    def test_requirement_change_stales_epic_and_every_feature(self, world: World) -> None:
        requirement = world.decomposed()
        first = world.get.execute(requirement.id)[0]
        approved = world.approve_current(requirement.id, first.id)
        world.clock.set(LATER)

        world.update.execute(
            FAKE_ACTORS[0],
            requirement.id,
            UpdateRequirementInput(title="Changed", description="Changed", expected_version=1),
        )

        features = world.get.execute(requirement.id)
        assert all(f.is_stale for f in features)
        assert all(
            f.staleness is not None and f.staleness.reason is StaleReason.REQUIREMENT_CHANGED
            for f in features
        )
        survivor = next(f for f in features if f.id == approved.id)
        assert survivor.status is FeatureStatus.APPROVED
        assert survivor.name == approved.name

    def test_epic_edit_stales_features_with_epic_changed(self, world: World) -> None:
        requirement = world.decomposed()
        world.clock.set(LATER)
        epic = world.epics.get_by_requirement_id(requirement.id)
        assert epic is not None

        world.edit_epic.execute(
            FAKE_ACTORS[0],
            requirement.id,
            EditEpicInput(
                name="n",
                outcome="o",
                business_case="c",
                expected_version=epic.version,
            ),
        )

        features = world.get.execute(requirement.id)
        assert all(
            f.staleness is not None and f.staleness.reason is StaleReason.EPIC_CHANGED
            for f in features
        )

    def test_epic_regeneration_stales_features(self, world: World) -> None:
        requirement = world.decomposed()
        world.clock.set(LATER)

        world.generate_epic.execute(FAKE_ACTORS[0], requirement.id, force=True)

        assert all(f.is_stale for f in world.get.execute(requirement.id))

    def test_features_survive_epic_regeneration_because_epic_id_is_stable(
        self, world: World
    ) -> None:
        """The prerequisite fix, proven from the Feature side."""
        requirement = world.decomposed()
        before = {f.id for f in world.get.execute(requirement.id)}

        world.generate_epic.execute(FAKE_ACTORS[0], requirement.id, force=True)

        assert {f.id for f in world.get.execute(requirement.id)} == before

    def test_a_stale_feature_cannot_be_approved(self, world: World) -> None:
        requirement = world.decomposed()
        first = world.get.execute(requirement.id)[0]
        world.update.execute(
            FAKE_ACTORS[0],
            requirement.id,
            UpdateRequirementInput(title="Changed", description="Changed", expected_version=1),
        )

        with pytest.raises(StaleFeatureApprovalError):
            world.approve_current(requirement.id, first.id)

    def test_editing_a_stale_feature_makes_it_approvable_again(self, world: World) -> None:
        requirement = world.decomposed()
        first = world.get.execute(requirement.id)[0]
        world.update.execute(
            FAKE_ACTORS[0],
            requirement.id,
            UpdateRequirementInput(title="Changed", description="Changed", expected_version=1),
        )

        world.edit.execute(
            FAKE_ACTORS[0],
            requirement.id,
            first.id,
            replace(EDIT, source_reconciled=True, expected_version=first.version + 1),
        )

        assert world.approve_current(requirement.id, first.id).status is FeatureStatus.APPROVED

    def test_cascade_is_harmless_when_no_features_exist(self, world: World) -> None:
        requirement = world.approved_epic_requirement()

        world.update.execute(
            FAKE_ACTORS[0],
            requirement.id,
            UpdateRequirementInput(title="Changed", description="Changed", expected_version=1),
        )

        epic = world.epics.get_by_requirement_id(requirement.id)
        assert epic is not None and epic.is_stale
        assert world.features.get_by_epic_id(EpicId(epic.id.value)) == []
