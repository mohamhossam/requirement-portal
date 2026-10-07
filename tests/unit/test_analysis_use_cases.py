"""Tests for analysis use cases."""

import pytest
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.errors import (
    RequirementAnalysisNotFoundError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.use_cases.analysis_collaboration import (
    AnalysisCollaboration,
)
from smb_requirement_agent.application.use_cases.analyze_requirement import AnalyzeRequirement
from smb_requirement_agent.application.use_cases.clarify_requirement_analysis import (
    ClarificationAnswerInput,
    ClarifyRequirementAnalysis,
)
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.application.use_cases.get_requirement_analysis import (
    GetRequirementAnalysis,
)
from smb_requirement_agent.application.use_cases.update_requirement import (
    UpdateRequirement,
    UpdateRequirementInput,
)
from smb_requirement_agent.domain.analysis.errors import (
    AnalysisClarificationConflictError,
)
from smb_requirement_agent.domain.analysis.value_objects import ClarificationKind
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.requirement.value_objects import (
    RequirementContext,
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.identity.domain.entities import RequirementAccess
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.identity.infrastructure.in_memory_identity import (
    InMemoryAccessRepository,
    InMemoryActorDirectory,
)
from smb_requirement_agent.infrastructure.llm.fake_requirement_analyzer import (
    FakeRequirementAnalyzer,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_analysis_audit_repository import (
    InMemoryAnalysisAuditRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_analysis_repository import (
    InMemoryRequirementAnalysisRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_document_repository import (
    InMemoryDocumentRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_epic_repository import (
    InMemoryEpicRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_feature_repository import (
    InMemoryFeatureRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_requirement_repository import (
    InMemoryRequirementRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_story_repository import (
    InMemoryStoryChangeProposalRepository,
    InMemoryStoryRepository,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.conftest import (
    TEST_NOW,
    AcceptAllSuggestionValidator,
    NoOpAnswerSuggestionScheduler,
    NoOpKnowledgeScheduler,
    make_analysis_documents,
    make_event_publisher,
)
from tests.reference_helpers import EmptyReferences
from tests.unit.access_service import access_service_for
from tests.unit.transaction_stub import NoOpTransactionManager


@pytest.fixture
def req_repo() -> InMemoryRequirementRepository:
    return InMemoryRequirementRepository()


@pytest.fixture
def analysis_repo() -> InMemoryRequirementAnalysisRepository:
    return InMemoryRequirementAnalysisRepository()


@pytest.fixture
def analyzer() -> FakeRequirementAnalyzer:
    return FakeRequirementAnalyzer()


@pytest.fixture
def existing_requirement(req_repo: InMemoryRequirementRepository) -> Requirement:
    req = Requirement(
        id=RequirementId("req-123"),
        title=RequirementTitle("Title"),
        description=RequirementDescription("Desc"),
        status=RequirementStatus.DRAFT,
        desired_outcome=RequirementContext("Outcome"),
    )
    req_repo.add(req)
    return req


@pytest.fixture
def collaboration(
    req_repo: InMemoryRequirementRepository,
    analysis_repo: InMemoryRequirementAnalysisRepository,
    analyzer: FakeRequirementAnalyzer,
    existing_requirement: Requirement,
) -> AnalysisCollaboration:
    access = InMemoryAccessRepository()
    access.save_requirement(
        RequirementAccess(existing_requirement.id).claim(FAKE_ACTORS[0], TEST_NOW)
    )
    audits = InMemoryAnalysisAuditRepository(lambda requirement_id: None)
    contexts = GenerationContextTokens(
        req_repo,
        analysis_repo,
        audits,
        InMemoryDocumentRepository(),
        InMemoryEpicRepository(),
        InMemoryFeatureRepository(),
        InMemoryStoryRepository(),
        InMemoryStoryChangeProposalRepository(),
        transactions=NoOpTransactionManager(),
        references=EmptyReferences(),
    )
    return AnalysisCollaboration(
        req_repo,
        analysis_repo,
        audits,
        analyzer,
        make_analysis_documents(),
        access,
        InMemoryActorDirectory(FAKE_ACTORS),
        FixedClock(TEST_NOW),
        NoOpTransactionManager(),
        NoOpKnowledgeScheduler(),
        NoOpAnswerSuggestionScheduler(),
        AcceptAllSuggestionValidator(),
        contexts=contexts,
        references=EmptyReferences(),
        reference_grounding=EmptyReferences(),
        authorization=access_service_for(req_repo, access),
    )


def test_analyze_requirement_success(
    req_repo: InMemoryRequirementRepository,
    analysis_repo: InMemoryRequirementAnalysisRepository,
    existing_requirement: Requirement,
    collaboration: AnalysisCollaboration,
) -> None:
    use_case = AnalyzeRequirement(collaboration)
    analysis = use_case.execute(FAKE_ACTORS[0], existing_requirement.id)

    assert analysis.requirement_id == existing_requirement.id
    assert len(analysis.known_facts) == 1
    assert analysis.known_facts[0].statement == "This is a known fact."

    # Verify it was saved
    saved = analysis_repo.get_by_requirement_id(existing_requirement.id)
    assert saved is not None


def test_answer_clarification_reanalyzes_and_preserves_human_context(
    req_repo: InMemoryRequirementRepository,
    analysis_repo: InMemoryRequirementAnalysisRepository,
    analyzer: FakeRequirementAnalyzer,
    existing_requirement: Requirement,
    collaboration: AnalysisCollaboration,
) -> None:
    current = AnalyzeRequirement(collaboration).execute(FAKE_ACTORS[0], existing_requirement.id)
    use_case = ClarifyRequirementAnalysis(collaboration)

    analysis = use_case.execute(
        existing_requirement.id,
        (
            ClarificationAnswerInput(
                ClarificationKind.OPEN_QUESTION,
                "Is this a question?",
                "The Product team owns the decision.",
            ),
        ),
        current.version,
        FAKE_ACTORS[0],
    )

    assert analysis.open_questions == ()
    assert analysis.clarifications[0].answer == "The Product team owns the decision."
    assert analyzer.received_clarifications == analysis.clarifications

    reanalyzed = AnalyzeRequirement(collaboration).execute(
        FAKE_ACTORS[0], existing_requirement.id, force=True
    )
    assert reanalyzed.clarifications == analysis.clarifications


def test_answer_rejects_item_from_an_outdated_analysis(
    req_repo: InMemoryRequirementRepository,
    analysis_repo: InMemoryRequirementAnalysisRepository,
    existing_requirement: Requirement,
    collaboration: AnalysisCollaboration,
) -> None:
    current = AnalyzeRequirement(collaboration).execute(FAKE_ACTORS[0], existing_requirement.id)
    use_case = ClarifyRequirementAnalysis(collaboration)

    with pytest.raises(AnalysisClarificationConflictError):
        use_case.execute(
            existing_requirement.id,
            (
                ClarificationAnswerInput(
                    ClarificationKind.OPEN_QUESTION,
                    "A question from an older page",
                    "Answer",
                ),
            ),
            current.version,
            FAKE_ACTORS[0],
        )


def test_analyze_requirement_not_found(
    req_repo: InMemoryRequirementRepository,
    analysis_repo: InMemoryRequirementAnalysisRepository,
    collaboration: AnalysisCollaboration,
) -> None:
    use_case = AnalyzeRequirement(collaboration)

    with pytest.raises(RequirementNotFoundError):
        use_case.execute(FAKE_ACTORS[0], RequirementId("non-existent"))


def test_get_requirement_analysis_success(
    req_repo: InMemoryRequirementRepository,
    analysis_repo: InMemoryRequirementAnalysisRepository,
    existing_requirement: Requirement,
    collaboration: AnalysisCollaboration,
) -> None:
    AnalyzeRequirement(collaboration).execute(FAKE_ACTORS[0], existing_requirement.id)

    use_case = GetRequirementAnalysis(req_repo, analysis_repo)
    analysis = use_case.execute(existing_requirement.id)

    assert analysis.requirement_id == existing_requirement.id


def test_get_requirement_analysis_not_found(
    req_repo: InMemoryRequirementRepository,
    analysis_repo: InMemoryRequirementAnalysisRepository,
    existing_requirement: Requirement,
) -> None:
    use_case = GetRequirementAnalysis(req_repo, analysis_repo)

    with pytest.raises(RequirementAnalysisNotFoundError):
        use_case.execute(existing_requirement.id)


def test_update_requirement_clears_analysis(
    req_repo: InMemoryRequirementRepository,
    analysis_repo: InMemoryRequirementAnalysisRepository,
    existing_requirement: Requirement,
    collaboration: AnalysisCollaboration,
) -> None:
    AnalyzeRequirement(collaboration).execute(FAKE_ACTORS[0], existing_requirement.id)

    access = InMemoryAccessRepository()
    access.save_requirement(
        RequirementAccess(existing_requirement.id).claim(FAKE_ACTORS[0], TEST_NOW)
    )
    update_use_case = UpdateRequirement(
        req_repo,
        make_event_publisher(analysis_repo),
        FixedClock(TEST_NOW),
        NoOpTransactionManager(),
        authorization=access_service_for(req_repo, access),
        documents=InMemoryDocumentRepository(),
    )
    update_use_case.execute(
        FAKE_ACTORS[0],
        existing_requirement.id,
        UpdateRequirementInput(title="New Title", description="New Desc", expected_version=1),
    )

    # Analysis should be deleted
    assert analysis_repo.get_by_requirement_id(existing_requirement.id) is None
