"""Stable, transport-neutral descriptions for expected application failures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from smb_requirement_agent.analysis.application.errors import (
    AnalysisConfirmationRequiredError,
    AnalysisRoundNotFoundError,
    ClarificationQuestionNotFoundError,
    DocumentContextTooLargeError,
    IntentProposalNotFoundError,
    RequirementAnalysisConflictError,
    RequirementAnalysisGenerationError,
    RequirementAnalysisNotFoundError,
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
from smb_requirement_agent.application.errors import (
    ArtifactVersionConflictError,
    AuthenticationRequiredError,
    DatabaseBusyError,
    DocumentExtractionBusyError,
    DocumentExtractionError,
    DocumentExtractionTimeoutError,
    IdentityProviderUnavailableError,
    KnowledgeGenerationError,
    ModelTransportError,
    PersistenceError,
    ServiceResponseError,
    ServiceUnavailableError,
    UnsupportedDocumentError,
)
from smb_requirement_agent.breakdown.application.errors import (
    ArchitectureJobNotFoundError,
    ArchitectureMappingConflictError,
    ArchitectureMappingProfileChangedError,
    EpicGenerationError,
    EpicNotFoundError,
    FeatureGenerationError,
    FeatureNotFoundError,
    FeaturesNotFoundError,
    StoryGenerationError,
    StoryNotFoundError,
    StoryProposalNotFoundError,
    StoryQualityEvaluationError,
    StoryQualitySnapshotConflictError,
    StoryQualitySnapshotNotFoundError,
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
from smb_requirement_agent.governance.application.errors import (
    ApprovalPolicyBlockedError,
    ApprovalWorkflowNotReadyError,
    BacklogExportFormatError,
    BreakdownReviewNotFoundError,
    BreakdownReviewStaleError,
    BreakdownRevisionNotExportableError,
    ReviewFlagNotFoundError,
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
from smb_requirement_agent.identity.application.errors import ActorNotFoundError
from smb_requirement_agent.identity.domain.errors import (
    AuthorizationDeniedError,
    InvalidIdentityError,
    RequirementAccessConflictError,
)
from smb_requirement_agent.jobs.application.errors import (
    AiJobNotFoundError,
    NotificationNotFoundError,
    ProviderBudgetExhaustedError,
    ProviderRateLimitExceededError,
)
from smb_requirement_agent.jobs.domain.errors import AiJobConflictError, InvalidAiJobError
from smb_requirement_agent.knowledge.application.errors import (
    AnswerSuggestionNotFoundError,
    KnowledgeFindingNotFoundError,
    KnowledgeIndexPendingError,
    KnowledgeScreenConflictError,
)
from smb_requirement_agent.knowledge.domain.screening_errors import (
    CorpusMembershipConflictError,
    KnowledgeFindingConflictError,
    KnowledgeReviewRequiredError,
    RequirementRetiredError,
)
from smb_requirement_agent.references.application.errors import (
    CitationNotCurrentError,
    KnowledgeViewUnavailableError,
)
from smb_requirement_agent.references.domain.architecture.catalogue import (
    InvalidArchitectureContentError,
)
from smb_requirement_agent.references.domain.architecture.knowledge import (
    InvalidRelationshipKindError,
    KnowledgeConflictError,
)
from smb_requirement_agent.references.domain.errors import InvalidKnowledgeError
from smb_requirement_agent.reporting.application.errors import (
    InvalidReportingWindowError,
    InvalidSavedViewError,
    SavedViewConflictError,
    SavedViewNotFoundError,
)
from smb_requirement_agent.requirements.application.errors import (
    DocumentNotFoundError,
    DocumentStorageError,
    DocumentVersionConflictError,
    DuplicateRequirementError,
    RequirementAnalysisIneligibleError,
    RequirementDraftNotFoundError,
    RequirementImpactAcknowledgementRequiredError,
    RequirementNotFoundError,
    RequirementVersionConflictError,
)
from smb_requirement_agent.requirements.domain.document.errors import (
    DocumentInclusionError,
    InvalidDocumentError,
)
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


class FailureCategory(StrEnum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    INVALID_INPUT = "invalid_input"
    PROVIDER = "provider"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    INTERNAL = "internal"


@dataclass(frozen=True)
class PublicError:
    code: str
    message: str
    category: FailureCategory
    retryable: bool


# Ordered most-specific first. This is the single catalogue consumed by HTTP
# delivery and durable job execution.
ERROR_CATALOGUE: tuple[tuple[type[Exception], str, FailureCategory], ...] = (
    (AuthenticationRequiredError, "authentication_required", FailureCategory.AUTHENTICATION),
    (AuthorizationDeniedError, "authorization_denied", FailureCategory.AUTHORIZATION),
    (ActorNotFoundError, "actor_not_found", FailureCategory.NOT_FOUND),
    (ProviderRateLimitExceededError, "provider_rate_limited", FailureCategory.RATE_LIMITED),
    (ProviderBudgetExhaustedError, "provider_budget_exhausted", FailureCategory.RATE_LIMITED),
    (AiJobNotFoundError, "ai_job_not_found", FailureCategory.NOT_FOUND),
    (NotificationNotFoundError, "notification_not_found", FailureCategory.NOT_FOUND),
    (SavedViewNotFoundError, "saved_view_not_found", FailureCategory.NOT_FOUND),
    (SavedViewConflictError, "saved_view_conflict", FailureCategory.CONFLICT),
    (InvalidSavedViewError, "invalid_saved_view", FailureCategory.INVALID_INPUT),
    (InvalidReportingWindowError, "invalid_reporting_window", FailureCategory.INVALID_INPUT),
    (
        BreakdownRevisionNotExportableError,
        "breakdown_revision_not_exportable",
        FailureCategory.CONFLICT,
    ),
    (BacklogExportFormatError, "backlog_export_format", FailureCategory.INVALID_INPUT),
    (AiJobConflictError, "ai_job_conflict", FailureCategory.CONFLICT),
    (InvalidAiJobError, "invalid_ai_job", FailureCategory.INVALID_INPUT),
    (RequirementAccessConflictError, "requirement_access_conflict", FailureCategory.CONFLICT),
    (InvalidIdentityError, "invalid_identity", FailureCategory.INVALID_INPUT),
    (
        IdentityProviderUnavailableError,
        "identity_provider_unavailable",
        FailureCategory.UNAVAILABLE,
    ),
    (
        ArchitectureJobNotFoundError,
        "architecture_job_not_found",
        FailureCategory.NOT_FOUND,
    ),
    (
        KnowledgeViewUnavailableError,
        "knowledge_view_unavailable",
        FailureCategory.NOT_FOUND,
    ),
    (
        KnowledgeConflictError,
        "architecture_knowledge_conflict",
        FailureCategory.CONFLICT,
    ),
    (
        ArchitectureMappingProfileChangedError,
        "architecture_knowledge_conflict",
        FailureCategory.CONFLICT,
    ),
    (
        InvalidRelationshipKindError,
        "invalid_architecture_knowledge",
        FailureCategory.INVALID_INPUT,
    ),
    (ArchitectureMappingConflictError, "architecture_mapping_conflict", FailureCategory.CONFLICT),
    # The specific reasons first: the first matching entry wins.
    (BreakdownReviewNotFoundError, "breakdown_review_not_found", FailureCategory.NOT_FOUND),
    (ReviewFlagNotFoundError, "review_flag_not_found", FailureCategory.NOT_FOUND),
    (BreakdownReviewStaleError, "breakdown_review_stale", FailureCategory.CONFLICT),
    (ApprovalWorkflowNotReadyError, "approval_workflow_not_ready", FailureCategory.CONFLICT),
    (ApprovalPolicyBlockedError, "approval_policy_blocked", FailureCategory.CONFLICT),
    (InvalidReviewTransitionError, "invalid_review_transition", FailureCategory.CONFLICT),
    (FlagResolutionConflictError, "flag_resolution_conflict", FailureCategory.CONFLICT),
    (FlagResolutionNotAllowedError, "flag_resolution_not_allowed", FailureCategory.CONFLICT),
    (InvalidReviewContentError, "invalid_review_content", FailureCategory.INVALID_INPUT),
    (InvalidApprovalContentError, "invalid_approval_content", FailureCategory.INVALID_INPUT),
    (InvalidArchitectureContentError, "invalid_architecture_content", FailureCategory.INTERNAL),
    (DocumentNotFoundError, "document_not_found", FailureCategory.NOT_FOUND),
    (UnsupportedDocumentError, "unsupported_document", FailureCategory.INVALID_INPUT),
    (DocumentExtractionError, "document_extraction", FailureCategory.INVALID_INPUT),
    (DocumentExtractionBusyError, "document_extraction_busy", FailureCategory.UNAVAILABLE),
    (DocumentExtractionTimeoutError, "document_extraction_timeout", FailureCategory.UNAVAILABLE),
    (DocumentContextTooLargeError, "document_context_too_large", FailureCategory.INVALID_INPUT),
    (DocumentInclusionError, "document_inclusion", FailureCategory.CONFLICT),
    (InvalidDocumentError, "invalid_document", FailureCategory.INVALID_INPUT),
    (DocumentStorageError, "document_storage", FailureCategory.INTERNAL),
    (DocumentVersionConflictError, "document_version_conflict", FailureCategory.CONFLICT),
    (RequirementNotFoundError, "requirement_not_found", FailureCategory.NOT_FOUND),
    (RequirementDraftNotFoundError, "requirement_draft_not_found", FailureCategory.NOT_FOUND),
    (RevisionNotFoundError, "revision_not_found", FailureCategory.NOT_FOUND),
    (InvalidRevisionError, "invalid_revision", FailureCategory.INVALID_INPUT),
    (RequirementAnalysisNotFoundError, "requirement_analysis_not_found", FailureCategory.NOT_FOUND),
    (AnalysisRoundNotFoundError, "analysis_round_not_found", FailureCategory.NOT_FOUND),
    (
        ClarificationQuestionNotFoundError,
        "clarification_question_not_found",
        FailureCategory.NOT_FOUND,
    ),
    (IntentProposalNotFoundError, "intent_proposal_not_found", FailureCategory.NOT_FOUND),
    (KnowledgeFindingNotFoundError, "knowledge_finding_not_found", FailureCategory.NOT_FOUND),
    (AnswerSuggestionNotFoundError, "answer_suggestion_not_found", FailureCategory.NOT_FOUND),
    (KnowledgeFindingConflictError, "knowledge_finding_conflict", FailureCategory.CONFLICT),
    (RequirementRetiredError, "requirement_retired", FailureCategory.CONFLICT),
    (CorpusMembershipConflictError, "corpus_membership_conflict", FailureCategory.CONFLICT),
    (KnowledgeScreenConflictError, "knowledge_screen_conflict", FailureCategory.CONFLICT),
    (KnowledgeReviewRequiredError, "knowledge_review_required", FailureCategory.CONFLICT),
    (DuplicateRequirementStateError, "duplicate_requirement_state", FailureCategory.CONFLICT),
    (InvalidKnowledgeError, "invalid_knowledge", FailureCategory.INVALID_INPUT),
    (KnowledgeIndexPendingError, "knowledge_index_pending", FailureCategory.UNAVAILABLE),
    (KnowledgeGenerationError, "knowledge_generation", FailureCategory.PROVIDER),
    (ModelTransportError, "model_transport", FailureCategory.PROVIDER),
    # A platform service (ADR-0099) could not be reached, or refused the request.
    (ServiceUnavailableError, "platform_service_unavailable", FailureCategory.UNAVAILABLE),
    (ServiceResponseError, "platform_service_refused", FailureCategory.PROVIDER),
    (RequirementAnalysisConflictError, "requirement_analysis_conflict", FailureCategory.CONFLICT),
    # References report a withdrawn citation as the analysis conflict clients already handle.
    (CitationNotCurrentError, "requirement_analysis_conflict", FailureCategory.CONFLICT),
    (AnalysisConfirmationRequiredError, "analysis_confirmation_required", FailureCategory.CONFLICT),
    (DuplicateRequirementError, "duplicate_requirement", FailureCategory.CONFLICT),
    (RequirementVersionConflictError, "requirement_version_conflict", FailureCategory.CONFLICT),
    (ArtifactVersionConflictError, "artifact_version_conflict", FailureCategory.CONFLICT),
    (
        RequirementImpactAcknowledgementRequiredError,
        "requirement_impact_acknowledgement_required",
        FailureCategory.CONFLICT,
    ),
    (
        RequirementAnalysisIneligibleError,
        "requirement_analysis_ineligible",
        FailureCategory.INVALID_INPUT,
    ),
    (InvalidRequirementTitleError, "invalid_requirement_title", FailureCategory.INVALID_INPUT),
    (
        RequirementIntakeTooLargeError,
        "requirement_intake_too_large",
        FailureCategory.INVALID_INPUT,
    ),
    (
        InvalidRequirementDescriptionError,
        "invalid_requirement_description",
        FailureCategory.INVALID_INPUT,
    ),
    (InvalidRequirementContextError, "invalid_requirement_context", FailureCategory.INVALID_INPUT),
    # A blank id reported as it was before RequirementId moved to the shared kernel (PR 2).
    (InvalidRequirementIdError, "invalid_requirement_context", FailureCategory.INVALID_INPUT),
    (InvalidRequirementVersionError, "invalid_requirement_version", FailureCategory.INVALID_INPUT),
    (InvalidClarificationError, "invalid_clarification", FailureCategory.INVALID_INPUT),
    (
        AnalysisClarificationConflictError,
        "analysis_clarification_conflict",
        FailureCategory.CONFLICT,
    ),
    (ClarificationVersionConflictError, "clarification_version_conflict", FailureCategory.CONFLICT),
    (
        InvalidClarificationTransitionError,
        "invalid_clarification_transition",
        FailureCategory.CONFLICT,
    ),
    (
        IntentProposalVersionConflictError,
        "intent_proposal_version_conflict",
        FailureCategory.CONFLICT,
    ),
    (
        InvalidIntentProposalTransitionError,
        "invalid_intent_proposal_transition",
        FailureCategory.CONFLICT,
    ),
    (
        InvalidIntentProposalDecisionError,
        "invalid_intent_proposal_decision",
        FailureCategory.INVALID_INPUT,
    ),
    (AnalysisConfirmationBlockedError, "analysis_confirmation_blocked", FailureCategory.CONFLICT),
    (InvalidAnalysisContentError, "invalid_analysis_content", FailureCategory.PROVIDER),
    (
        RequirementAnalysisGenerationError,
        "requirement_analysis_generation",
        FailureCategory.PROVIDER,
    ),
    (EpicNotFoundError, "epic_not_found", FailureCategory.NOT_FOUND),
    (EpicRegenerationConflictError, "epic_regeneration_conflict", FailureCategory.CONFLICT),
    (StaleEpicApprovalError, "stale_epic_approval", FailureCategory.CONFLICT),
    (InvalidEpicContentError, "invalid_epic_content", FailureCategory.INVALID_INPUT),
    (EpicGenerationError, "epic_generation", FailureCategory.PROVIDER),
    (EpicNotApprovedError, "epic_not_approved", FailureCategory.CONFLICT),
    (FeatureNotFoundError, "feature_not_found", FailureCategory.NOT_FOUND),
    (FeaturesNotFoundError, "features_not_found", FailureCategory.NOT_FOUND),
    (FeatureRegenerationConflictError, "feature_regeneration_conflict", FailureCategory.CONFLICT),
    (StaleFeatureApprovalError, "stale_feature_approval", FailureCategory.CONFLICT),
    (InvalidFeatureContentError, "invalid_feature_content", FailureCategory.INVALID_INPUT),
    (FeatureGenerationError, "feature_generation", FailureCategory.PROVIDER),
    (StoryNotFoundError, "story_not_found", FailureCategory.NOT_FOUND),
    (
        StoryQualitySnapshotConflictError,
        "story_quality_snapshot_conflict",
        FailureCategory.CONFLICT,
    ),
    (
        StoryQualitySnapshotNotFoundError,
        "story_quality_snapshot_not_found",
        FailureCategory.NOT_FOUND,
    ),
    (StoryProposalNotFoundError, "story_proposal_not_found", FailureCategory.NOT_FOUND),
    (StoriesAlreadyExistError, "stories_already_exist", FailureCategory.CONFLICT),
    (StoryRegenerationConflictError, "story_regeneration_conflict", FailureCategory.CONFLICT),
    (FeatureNotReadyForStoriesError, "feature_not_ready_for_stories", FailureCategory.CONFLICT),
    (StoryProposalConflictError, "story_proposal_conflict", FailureCategory.CONFLICT),
    (InvalidStoryContentError, "invalid_story_content", FailureCategory.INVALID_INPUT),
    (StoryGenerationError, "story_generation", FailureCategory.PROVIDER),
    (StoryQualityEvaluationError, "story_quality_evaluation", FailureCategory.PROVIDER),
    (InvalidGeneratedContentError, "invalid_generated_content", FailureCategory.INTERNAL),
    (DatabaseBusyError, "database_busy", FailureCategory.UNAVAILABLE),
    (PersistenceError, "persistence", FailureCategory.INTERNAL),
)


def describe_public_error(exc: Exception) -> PublicError:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ModelTransportError):
            return PublicError(
                "model_" + current.kind,
                str(current),
                FailureCategory.PROVIDER,
                current.kind not in {"authentication", "configuration", "index_required"},
            )
        current = current.__cause__
    for error_type, code, category in ERROR_CATALOGUE:
        if isinstance(exc, error_type):
            safe = category not in {
                FailureCategory.INTERNAL,
                FailureCategory.PROVIDER,
                FailureCategory.UNAVAILABLE,
            }
            return PublicError(
                code,
                str(exc) if safe else "The service could not complete the request.",
                category,
                category
                in {
                    FailureCategory.PROVIDER,
                    FailureCategory.UNAVAILABLE,
                    FailureCategory.RATE_LIMITED,
                },
            )
    return PublicError(
        "internal", "The service could not complete the request.", FailureCategory.INTERNAL, False
    )
