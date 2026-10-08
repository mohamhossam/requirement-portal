"""Tests for the Epic use cases and derived-artifact invalidation."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.analysis.application.use_cases.analysis_collaboration import (
    AnalysisCollaboration,
)
from smb_requirement_agent.analysis.application.use_cases.analyze_requirement import (
    AnalyzeRequirement,
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
    AnalysisConfirmationRequiredError,
    EpicNotFoundError,
    RequirementAnalysisNotFoundError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.use_cases.approval_workflow import ApprovalRecorder
from smb_requirement_agent.application.use_cases.approve_epic import ApproveEpic
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.breakdown.application.use_cases.edit_epic import EditEpic, EditEpicInput
from smb_requirement_agent.breakdown.application.use_cases.generate_epic import GenerateEpic
from smb_requirement_agent.breakdown.application.use_cases.get_epic import GetEpic
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.breakdown.domain.epic.errors import (
    EpicRegenerationConflictError,
    StaleEpicApprovalError,
)
from smb_requirement_agent.breakdown.domain.epic.value_objects import EpicStatus, StaleReason
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
from smb_requirement_agent.breakdown.infrastructure.llm.fake_epic_generator import (
    FAKE_MODEL,
    FAKE_PROMPT_VERSION,
    FakeEpicGenerator,
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
from tests.conftest import (
    AcceptAllSuggestionValidator,
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

EDIT = EditEpicInput(
    name="Human name", outcome="Human outcome", business_case="Human business case"
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
        self.generator = FakeEpicGenerator()
        self.clock = FixedClock(GENERATED_AT)
        self.audits = InMemoryAnalysisAuditRepository(lambda requirement_id: None)
        self.reviews = InMemoryBreakdownReviewRepository()
        self.access = InMemoryAccessRepository()

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
        self.events = make_event_publisher(
            self.analyses,
            self.epics,
            self.features,
            self.stories,
            self.clock,
            self.audits,
            reviews=self.reviews,
        )
        self.generate = GenerateEpic(
            self.requirements,
            self.analyses,
            self.epics,
            self.generator,
            self.clock,
            self.events,
            NoOpTransactionManager(),
            authorization=access_service_for(self.requirements, self.access),
            contexts=self.contexts,
        )
        self.get = GetEpic(self.requirements, self.epics)
        self.edit = EditEpic(
            self.requirements,
            self.epics,
            self.events,
            NoOpTransactionManager(),
            authorization=access_service_for(self.requirements, self.access),
        )
        self.approve = ApproveEpic(
            self.requirements,
            self.epics,
            ApprovalRecorder(
                self.access, self.clock, access_service_for(self.requirements, self.access)
            ),
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

    def analysed_requirement(self) -> Requirement:
        requirement = self.create.execute(
            CreateRequirementInput(
                title="Bundle ordering",
                description="Order bundles in channel",
                desired_outcome="Customers can order bundles in channel.",
            )
        )
        analysis = self.analyze.execute(FAKE_ACTORS[0], requirement.id)
        resolved = replace(
            analysis,
            assumptions=(),
            open_questions=(),
            ambiguities=(),
            potential_dependencies=(),
        )
        self.analyses.save(resolved.confirm(self.clock.now(), FAKE_ACTORS[0]))
        return requirement

    def approve_current(self, requirement_id: RequirementId) -> Epic:
        epic = self.get.execute(requirement_id)
        return self.approve.execute(
            requirement_id,
            FAKE_ACTORS[0],
            epic.version,
            artifact_fingerprint(epic),
        )


@pytest.fixture
def world() -> World:
    return World()


class TestGenerateEpic:
    def test_refuses_an_unconfirmed_analysis(self, world: World) -> None:
        requirement = world.create.execute(
            CreateRequirementInput(title="Bundle ordering", description="Order bundles in channel")
        )
        world.analyze.execute(FAKE_ACTORS[0], requirement.id)

        with pytest.raises(AnalysisConfirmationRequiredError):
            world.generate.execute(FAKE_ACTORS[0], requirement.id)

    def test_generates_from_an_analysed_requirement(self, world: World) -> None:
        requirement = world.analysed_requirement()

        result = world.generate.execute(FAKE_ACTORS[0], requirement.id)

        assert result.replaced_existing is False
        assert result.epic.status is EpicStatus.GENERATED
        assert result.epic.requirement_id == requirement.id
        assert not result.epic.is_stale

    def test_stamps_provenance_from_the_clock_and_adapter(self, world: World) -> None:
        requirement = world.analysed_requirement()

        epic = world.generate.execute(FAKE_ACTORS[0], requirement.id).epic

        assert epic.provenance.generated_at == GENERATED_AT
        assert epic.provenance.model == FAKE_MODEL
        assert epic.provenance.prompt_version == FAKE_PROMPT_VERSION

    def test_unanalysed_requirement_cannot_produce_an_epic(self, world: World) -> None:
        """The analysis is a required input, not optional enrichment."""
        requirement = world.create.execute(
            CreateRequirementInput(title="Unanalysed", description="No analysis yet")
        )

        with pytest.raises(RequirementAnalysisNotFoundError):
            world.generate.execute(FAKE_ACTORS[0], requirement.id)

    def test_unknown_requirement_raises(self, world: World) -> None:
        with pytest.raises(RequirementNotFoundError):
            world.generate.execute(FAKE_ACTORS[0], RequirementId("missing"))

    def test_regenerating_untouched_content_is_allowed(self, world: World) -> None:
        requirement = world.analysed_requirement()
        world.generate.execute(FAKE_ACTORS[0], requirement.id)

        result = world.generate.execute(FAKE_ACTORS[0], requirement.id)

        assert result.replaced_existing is True

    @pytest.mark.parametrize("make_human_owned", ["edit", "approve"])
    def test_regenerating_human_owned_content_is_refused(
        self, world: World, make_human_owned: str
    ) -> None:
        requirement = world.analysed_requirement()
        world.generate.execute(FAKE_ACTORS[0], requirement.id)
        if make_human_owned == "edit":
            world.edit.execute(FAKE_ACTORS[0], requirement.id, EDIT)
        else:
            world.approve_current(requirement.id)

        with pytest.raises(EpicRegenerationConflictError):
            world.generate.execute(FAKE_ACTORS[0], requirement.id)

    def test_force_replaces_human_owned_content(self, world: World) -> None:
        requirement = world.analysed_requirement()
        world.generate.execute(FAKE_ACTORS[0], requirement.id)
        world.approve_current(requirement.id)

        result = world.generate.execute(FAKE_ACTORS[0], requirement.id, force=True)

        assert result.epic.status is EpicStatus.GENERATED
        assert result.replaced_existing is True


class TestGetEditApprove:
    def test_get_returns_the_stored_epic(self, world: World) -> None:
        requirement = world.analysed_requirement()
        generated = world.generate.execute(FAKE_ACTORS[0], requirement.id).epic

        assert world.get.execute(requirement.id).id == generated.id

    def test_get_without_an_epic_raises(self, world: World) -> None:
        requirement = world.analysed_requirement()

        with pytest.raises(EpicNotFoundError):
            world.get.execute(requirement.id)

    def test_edit_persists_and_marks_edited(self, world: World) -> None:
        requirement = world.analysed_requirement()
        world.generate.execute(FAKE_ACTORS[0], requirement.id)

        edited = world.edit.execute(FAKE_ACTORS[0], requirement.id, EDIT)

        assert edited.status is EpicStatus.EDITED
        assert world.get.execute(requirement.id).name.value == "Human name"

    def test_approve_persists(self, world: World) -> None:
        requirement = world.analysed_requirement()
        world.generate.execute(FAKE_ACTORS[0], requirement.id)

        world.approve_current(requirement.id)

        assert world.get.execute(requirement.id).status is EpicStatus.APPROVED


class TestInvalidationOnRequirementUpdate:
    def test_analysis_is_deleted_and_epic_is_flagged_not_destroyed(self, world: World) -> None:
        """The regression test for the slice's central decision."""
        requirement = world.analysed_requirement()
        world.generate.execute(FAKE_ACTORS[0], requirement.id)
        approved = world.approve_current(requirement.id)
        world.clock.set(LATER)

        world.update.execute(
            FAKE_ACTORS[0],
            requirement.id,
            UpdateRequirementInput(title="Changed", description="Changed text", expected_version=1),
        )

        assert world.analyses.get_by_requirement_id(requirement.id) is None

        epic = world.get.execute(requirement.id)
        assert epic.status is EpicStatus.APPROVED
        assert epic.name == approved.name
        assert epic.business_case == approved.business_case
        assert epic.is_stale
        assert epic.staleness is not None
        assert epic.staleness.reason is StaleReason.REQUIREMENT_CHANGED
        assert epic.staleness.since == LATER

    def test_a_stale_epic_cannot_be_approved(self, world: World) -> None:
        requirement = world.analysed_requirement()
        world.generate.execute(FAKE_ACTORS[0], requirement.id)
        world.update.execute(
            FAKE_ACTORS[0],
            requirement.id,
            UpdateRequirementInput(title="Changed", description="Changed text", expected_version=1),
        )

        with pytest.raises(StaleEpicApprovalError):
            world.approve_current(requirement.id)

    def test_editing_a_stale_epic_makes_it_approvable_again(self, world: World) -> None:
        requirement = world.analysed_requirement()
        world.generate.execute(FAKE_ACTORS[0], requirement.id)
        world.update.execute(
            FAKE_ACTORS[0],
            requirement.id,
            UpdateRequirementInput(title="Changed", description="Changed text", expected_version=1),
        )

        epic = world.get.execute(requirement.id)
        world.edit.execute(
            FAKE_ACTORS[0],
            requirement.id,
            replace(EDIT, source_reconciled=True, expected_version=epic.version),
        )

        assert world.approve_current(requirement.id).status is EpicStatus.APPROVED

    def test_invalidation_is_harmless_when_nothing_is_derived(self, world: World) -> None:
        requirement = world.create.execute(
            CreateRequirementInput(title="Bare", description="No analysis, no epic")
        )

        world.update.execute(
            FAKE_ACTORS[0],
            requirement.id,
            UpdateRequirementInput(title="Changed", description="Changed text", expected_version=1),
        )

        assert world.epics.get_by_requirement_id(requirement.id) is None


class TestEpicIdentity:
    def test_epic_id_is_stable_across_forced_regeneration(self, world: World) -> None:
        """Anything referencing the Epic must survive its text being regenerated."""
        requirement = world.analysed_requirement()
        original = world.generate.execute(FAKE_ACTORS[0], requirement.id).epic
        world.approve_current(requirement.id)

        regenerated = world.generate.execute(FAKE_ACTORS[0], requirement.id, force=True).epic

        assert regenerated.id == original.id

    def test_epic_id_is_stable_across_plain_regeneration(self, world: World) -> None:
        requirement = world.analysed_requirement()
        original = world.generate.execute(FAKE_ACTORS[0], requirement.id).epic

        assert world.generate.execute(FAKE_ACTORS[0], requirement.id).epic.id == original.id


def test_direct_epic_commands_reject_an_unrelated_actor(world: World) -> None:
    from smb_requirement_agent.identity.domain.errors import AuthorizationDeniedError

    requirement = world.analysed_requirement()
    with pytest.raises(AuthorizationDeniedError):
        world.generate.execute(FAKE_ACTORS[1], requirement.id)
    assert world.epics.get_by_requirement_id(requirement.id) is None

    epic = world.generate.execute(FAKE_ACTORS[0], requirement.id).epic
    with pytest.raises(AuthorizationDeniedError):
        world.edit.execute(FAKE_ACTORS[1], requirement.id, EDIT)
    assert world.epics.get_by_requirement_id(requirement.id) == epic
