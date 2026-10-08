"""Tests for the central domain-error to HTTP-status mapping."""

import logging
from collections.abc import Generator, Sequence

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    ActiveQuestionContext,
    AnalysisDocumentContext,
    RequirementAnalysisCandidate,
    RequirementAnalyzerPort,
)
from smb_requirement_agent.analysis.domain.errors import (
    AnalysisClarificationConflictError,
    AnalysisConfirmationBlockedError,
    ClarificationVersionConflictError,
    IntentProposalVersionConflictError,
    InvalidAnalysisContentError,
    InvalidClarificationError,
    InvalidClarificationTransitionError,
    InvalidIntentProposalDecisionError,
    InvalidIntentProposalTransitionError,
)
from smb_requirement_agent.analysis.domain.value_objects import HumanClarification, IntentProposal
from smb_requirement_agent.application.errors import (
    ActorNotFoundError,
    AiJobNotFoundError,
    AnalysisConfirmationRequiredError,
    AnalysisRoundNotFoundError,
    AnswerSuggestionNotFoundError,
    ApprovalPolicyBlockedError,
    ApprovalWorkflowNotReadyError,
    ArchitectureJobNotFoundError,
    ArchitectureMappingConflictError,
    ArchitectureMappingProfileChangedError,
    ArtifactVersionConflictError,
    AuthenticationRequiredError,
    BacklogExportFormatError,
    BreakdownReviewNotFoundError,
    BreakdownReviewStaleError,
    BreakdownRevisionNotExportableError,
    ClarificationQuestionNotFoundError,
    DocumentContextTooLargeError,
    DocumentExtractionBusyError,
    DocumentExtractionError,
    DocumentExtractionTimeoutError,
    DocumentNotFoundError,
    DocumentStorageError,
    DocumentVersionConflictError,
    DuplicateRequirementError,
    EpicGenerationError,
    EpicNotFoundError,
    FeatureGenerationError,
    FeatureNotFoundError,
    FeaturesNotFoundError,
    IdentityProviderUnavailableError,
    IntentProposalNotFoundError,
    InvalidReportingWindowError,
    InvalidSavedViewError,
    KnowledgeFindingNotFoundError,
    KnowledgeGenerationError,
    KnowledgeIndexPendingError,
    KnowledgeScreenConflictError,
    KnowledgeViewUnavailableError,
    ModelTransportError,
    NotificationNotFoundError,
    PersistenceError,
    ProviderRateLimitExceededError,
    RequirementAnalysisConflictError,
    RequirementAnalysisGenerationError,
    RequirementAnalysisIneligibleError,
    RequirementAnalysisNotFoundError,
    RequirementDraftNotFoundError,
    RequirementImpactAcknowledgementRequiredError,
    RequirementNotFoundError,
    RequirementVersionConflictError,
    ReviewFlagNotFoundError,
    SavedViewConflictError,
    SavedViewNotFoundError,
    ServiceResponseError,
    ServiceUnavailableError,
    StoryGenerationError,
    StoryNotFoundError,
    StoryProposalNotFoundError,
    StoryQualityEvaluationError,
    StoryQualitySnapshotConflictError,
    StoryQualitySnapshotNotFoundError,
    UnsupportedDocumentError,
)
from smb_requirement_agent.application.public_errors import (
    FailureCategory,
    describe_public_error,
)
from smb_requirement_agent.breakdown.domain.epic.errors import (
    EpicNotApprovedError,
    EpicRegenerationConflictError,
    InvalidEpicContentError,
    StaleEpicApprovalError,
)
from smb_requirement_agent.breakdown.domain.feature.errors import (
    FeatureRegenerationConflictError,
    InvalidFeatureContentError,
    StaleFeatureApprovalError,
)
from smb_requirement_agent.breakdown.domain.story.errors import (
    FeatureNotReadyForStoriesError,
    InvalidStoryContentError,
    StoriesAlreadyExistError,
    StoryProposalConflictError,
    StoryRegenerationConflictError,
)
from smb_requirement_agent.domain.architecture.catalogue import InvalidArchitectureContentError
from smb_requirement_agent.domain.architecture.knowledge import (
    InvalidRelationshipKindError,
    KnowledgeConflictError,
)
from smb_requirement_agent.domain.knowledge.errors import InvalidKnowledgeError
from smb_requirement_agent.domain.knowledge.screening_errors import (
    CorpusMembershipConflictError,
    KnowledgeFindingConflictError,
    KnowledgeReviewRequiredError,
    RequirementRetiredError,
)
from smb_requirement_agent.governance.domain.review.errors import (
    FlagResolutionConflictError,
    FlagResolutionNotAllowedError,
    InvalidReviewContentError,
    InvalidReviewTransitionError,
)
from smb_requirement_agent.governance.domain.revision.errors import (
    InvalidRevisionError,
    RevisionNotFoundError,
)
from smb_requirement_agent.identity.domain.errors import (
    AuthorizationDeniedError,
    InvalidIdentityError,
    RequirementAccessConflictError,
)
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.error_handlers import (
    ERROR_STATUS_CODES,
    status_code_for,
)
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.jobs.domain.errors import AiJobConflictError, InvalidAiJobError
from smb_requirement_agent.requirements.domain.document.errors import (
    DocumentInclusionError,
    InvalidDocumentError,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.errors import (
    DuplicateRequirementStateError,
    InvalidRequirementContextError,
    InvalidRequirementDescriptionError,
    InvalidRequirementTitleError,
    InvalidRequirementVersionError,
    RequirementIntakeTooLargeError,
)
from smb_requirement_agent.shared_kernel.errors import (
    InvalidApprovalContentError,
    InvalidGeneratedContentError,
    InvalidRequirementIdError,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.conftest import FAKE_PROVIDER_SETTINGS


class BlankOutputAnalyzer(RequirementAnalyzerPort):
    """An analyzer that fails to strip blank entries from provider output.

    Stands in for any adapter that lets unusable content through: the resulting
    domain error must still be mapped, not escape as a 500.
    """

    def analyze(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext] = (),
        intent_decisions: Sequence[IntentProposal] = (),
        active_questions: Sequence[ActiveQuestionContext] = (),
    ) -> RequirementAnalysisCandidate:
        return RequirementAnalysisCandidate(
            known_facts=["   "],
            constraints=[],
            business_rules=[],
            assumptions=[],
            open_questions=[],
            ambiguities=[],
            potential_dependencies=[],
            intent_proposals=[],
            model="malformed-test-analyzer",
            prompt_version="malformed-test-v1",
        )


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """A client whose analyzer returns content the domain will reject."""
    container = build_container(FAKE_PROVIDER_SETTINGS, analyzer=BlankOutputAnalyzer())
    with TestClient(create_app(lambda: container)) as c:
        yield c


# The status code every mapped error is expected to produce. AGENTS.md requires
# a new error type to be added to the map and to this table in the same commit;
# test_every_mapped_error_is_covered turns that rule into a failing build.
EXPECTED_STATUS_CODES: dict[type[Exception], int] = {
    AuthenticationRequiredError: 401,
    AuthorizationDeniedError: 403,
    ActorNotFoundError: 404,
    AiJobNotFoundError: 404,
    AnswerSuggestionNotFoundError: 404,
    KnowledgeFindingNotFoundError: 404,
    NotificationNotFoundError: 404,
    SavedViewNotFoundError: 404,
    SavedViewConflictError: 409,
    InvalidSavedViewError: 422,
    InvalidReportingWindowError: 422,
    BreakdownRevisionNotExportableError: 409,
    BacklogExportFormatError: 422,
    AiJobConflictError: 409,
    KnowledgeFindingConflictError: 409,
    RequirementRetiredError: 409,
    CorpusMembershipConflictError: 409,
    KnowledgeScreenConflictError: 409,
    KnowledgeReviewRequiredError: 409,
    DuplicateRequirementStateError: 409,
    InvalidKnowledgeError: 422,
    KnowledgeGenerationError: 502,
    KnowledgeIndexPendingError: 503,
    ModelTransportError: 502,
    ServiceUnavailableError: 503,
    ServiceResponseError: 502,
    InvalidAiJobError: 422,
    RequirementAccessConflictError: 409,
    InvalidIdentityError: 422,
    IdentityProviderUnavailableError: 503,
    ArchitectureJobNotFoundError: 404,
    KnowledgeViewUnavailableError: 404,
    KnowledgeConflictError: 409,
    InvalidRelationshipKindError: 422,
    ArchitectureMappingConflictError: 409,
    ArchitectureMappingProfileChangedError: 409,
    BreakdownReviewNotFoundError: 404,
    ReviewFlagNotFoundError: 404,
    BreakdownReviewStaleError: 409,
    ApprovalWorkflowNotReadyError: 409,
    ApprovalPolicyBlockedError: 409,
    InvalidReviewTransitionError: 409,
    FlagResolutionConflictError: 409,
    FlagResolutionNotAllowedError: 409,
    InvalidReviewContentError: 422,
    InvalidApprovalContentError: 422,
    InvalidArchitectureContentError: 500,
    DocumentNotFoundError: 404,
    UnsupportedDocumentError: 422,
    DocumentExtractionError: 422,
    DocumentExtractionBusyError: 503,
    DocumentExtractionTimeoutError: 503,
    DocumentContextTooLargeError: 422,
    DocumentInclusionError: 409,
    InvalidDocumentError: 422,
    DocumentStorageError: 500,
    DocumentVersionConflictError: 409,
    RequirementNotFoundError: 404,
    RequirementDraftNotFoundError: 404,
    RequirementAnalysisNotFoundError: 404,
    AnalysisRoundNotFoundError: 404,
    ClarificationQuestionNotFoundError: 404,
    IntentProposalNotFoundError: 404,
    RequirementAnalysisConflictError: 409,
    AnalysisConfirmationRequiredError: 409,
    DuplicateRequirementError: 409,
    RequirementVersionConflictError: 409,
    ArtifactVersionConflictError: 409,
    RequirementImpactAcknowledgementRequiredError: 409,
    RequirementAnalysisIneligibleError: 422,
    InvalidRequirementTitleError: 422,
    InvalidRequirementDescriptionError: 422,
    InvalidRequirementContextError: 422,
    InvalidRequirementIdError: 422,
    InvalidRequirementVersionError: 422,
    InvalidClarificationError: 422,
    InvalidClarificationTransitionError: 409,
    IntentProposalVersionConflictError: 409,
    InvalidIntentProposalTransitionError: 409,
    InvalidIntentProposalDecisionError: 422,
    ClarificationVersionConflictError: 409,
    AnalysisClarificationConflictError: 409,
    AnalysisConfirmationBlockedError: 409,
    InvalidAnalysisContentError: 502,
    RequirementAnalysisGenerationError: 502,
    EpicNotFoundError: 404,
    EpicRegenerationConflictError: 409,
    StaleEpicApprovalError: 409,
    InvalidEpicContentError: 422,
    EpicGenerationError: 502,
    InvalidGeneratedContentError: 500,
    EpicNotApprovedError: 409,
    FeatureNotFoundError: 404,
    FeaturesNotFoundError: 404,
    FeatureRegenerationConflictError: 409,
    StaleFeatureApprovalError: 409,
    InvalidFeatureContentError: 422,
    FeatureGenerationError: 502,
    RevisionNotFoundError: 404,
    InvalidRevisionError: 422,
    StoryNotFoundError: 404,
    StoryProposalNotFoundError: 404,
    StoryQualityEvaluationError: 502,
    StoryQualitySnapshotConflictError: 409,
    StoryQualitySnapshotNotFoundError: 404,
    StoriesAlreadyExistError: 409,
    StoryRegenerationConflictError: 409,
    FeatureNotReadyForStoriesError: 409,
    StoryProposalConflictError: 409,
    InvalidStoryContentError: 422,
    StoryGenerationError: 502,
    PersistenceError: 500,
    ProviderRateLimitExceededError: 429,
    RequirementIntakeTooLargeError: 422,
}


@pytest.mark.parametrize(
    ("error_type", "expected"),
    list(EXPECTED_STATUS_CODES.items()),
    ids=lambda value: value.__name__ if isinstance(value, type) else str(value),
)
def test_known_errors_are_mapped(error_type: type[Exception], expected: int) -> None:
    # A refusal carries the other service's status and detail.
    error = error_type(422, "boom") if error_type is ServiceResponseError else error_type("boom")
    assert status_code_for(error) == expected


def test_every_mapped_error_is_covered() -> None:
    """Adding an error to the map without a status assertion must fail the build."""
    mapped = {error_type for error_type, _ in ERROR_STATUS_CODES}

    assert mapped == set(EXPECTED_STATUS_CODES)


def test_unmapped_errors_are_not_claimed() -> None:
    assert status_code_for(ValueError("unrelated")) is None


def test_blank_requirement_id_keeps_its_public_error() -> None:
    """RequirementId moved to the shared kernel (ADR-0103, PR 2); clients see no difference."""
    with pytest.raises(InvalidRequirementIdError) as raised:
        RequirementId("   ")

    error = describe_public_error(raised.value)

    assert error.code == "invalid_requirement_context"
    assert error.category is FailureCategory.INVALID_INPUT
    assert error.message == "Requirement id must not be blank."
    assert status_code_for(raised.value) == 422


def test_public_error_catalogue_preserves_caller_messages_and_hides_server_details() -> None:
    caller_error = describe_public_error(
        RequirementVersionConflictError("Requirement changed; reload it.")
    )
    server_error = describe_public_error(PersistenceError("password=secret host=private"))

    assert caller_error.category is FailureCategory.CONFLICT
    assert caller_error.message == "Requirement changed; reload it."
    assert caller_error.code == "requirement_version_conflict"
    assert server_error.category is FailureCategory.INTERNAL
    assert server_error.message == "The service could not complete the request."
    assert "secret" not in server_error.message


def test_invalid_analysis_content_surfaces_as_502_not_500(client: TestClient) -> None:
    headers = {"X-Fake-Actor-Id": "fake-owner"}
    created = client.post("/requirements", json={"title": "T", "description": "D"}, headers=headers)
    requirement_id = created.json()["id"]
    requirement = client.get(f"/requirements/{requirement_id}", headers=headers).json()

    response = client.post(
        f"/requirements/{requirement_id}/analysis",
        json={"context_token": requirement["analysis_context_token"]},
        headers=headers,
    )

    assert response.status_code == 502
    assert set(response.json()) == {"code", "message", "correlation_id"}
    assert response.json()["message"] == "The service could not complete the request."


def test_mapped_server_error_is_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    headers = {"X-Fake-Actor-Id": "fake-owner"}
    created = client.post("/requirements", json={"title": "T", "description": "D"}, headers=headers)
    requirement_id = created.json()["id"]
    requirement = client.get(f"/requirements/{requirement_id}", headers=headers).json()

    with caplog.at_level(logging.ERROR, logger="smb_requirement_agent.api.errors"):
        response = client.post(
            f"/requirements/{requirement_id}/analysis",
            json={"context_token": requirement["analysis_context_token"]},
            headers=headers,
        )

    assert response.status_code == 502
    assert "POST" in caplog.text
    assert f"/requirements/{requirement_id}/analysis" in caplog.text
    assert "InvalidAnalysisContentError" in caplog.text
