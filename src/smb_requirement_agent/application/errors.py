"""Application failures caused by orchestration or external boundaries."""

from smb_requirement_agent.domain.analysis.errors import RequirementAnalysisError
from smb_requirement_agent.domain.epic.errors import EpicError
from smb_requirement_agent.domain.feature.errors import FeatureError
from smb_requirement_agent.domain.requirement.errors import RequirementError
from smb_requirement_agent.domain.story.errors import StoryError


class RequirementNotFoundError(RequirementError):
    """A requested Requirement does not exist in the repository."""


class DuplicateRequirementError(RequirementError):
    """A repository already contains the requested Requirement identity."""


class RequirementDraftNotFoundError(RequirementError):
    """A requested resumable draft does not exist."""


class RequirementVersionConflictError(RequirementError):
    """An optimistic source edit used a stale version."""


class ArtifactVersionConflictError(Exception):
    """A generated artifact mutation used a stale aggregate version."""


class ArchitectureJobNotFoundError(Exception):
    """An architecture job does not exist."""


class ProviderRateLimitExceededError(Exception):
    """An actor started more provider-calling operations than the rate limit allows."""

    def __init__(self, message: str, retry_after_seconds: int = 60) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class RequirementImpactAcknowledgementRequiredError(RequirementError):
    """A source edit would invalidate generated content without acknowledgement."""


class RequirementAnalysisIneligibleError(RequirementError):
    """A Requirement is missing source fields required for analysis."""


class RequirementAnalysisNotFoundError(RequirementAnalysisError):
    """A requested analysis does not exist in the repository."""


class RequirementAnalysisGenerationError(RequirementAnalysisError):
    """The configured analysis provider failed or returned unusable content."""


class RequirementAnalysisConflictError(RequirementAnalysisError):
    """Analysis generation targeted state that changed or requires explicit force."""


class AnalysisRoundNotFoundError(RequirementAnalysisError):
    """A requested immutable analysis round does not exist."""


class ClarificationQuestionNotFoundError(RequirementAnalysisError):
    """A requested clarification question does not exist."""


class IntentProposalNotFoundError(RequirementAnalysisError):
    """A requested intent proposal does not exist in the current analysis."""


class AnalysisConfirmationRequiredError(RequirementAnalysisError):
    """Backlog generation was requested before the analysis was confirmed."""


class EpicNotFoundError(EpicError):
    """A requested Epic does not exist in the repository."""


class EpicGenerationError(EpicError):
    """The configured Epic provider failed or returned unusable content."""


class FeatureNotFoundError(FeatureError):
    """A requested Feature does not exist in the repository."""


class FeaturesNotFoundError(FeatureError):
    """No Feature collection exists for the requested Epic."""


class FeatureGenerationError(FeatureError):
    """The configured Feature provider failed or returned unusable content."""


class StoryNotFoundError(StoryError):
    """A requested Story does not exist in the repository."""


class StoryGenerationError(StoryError):
    """The configured Story provider failed or returned unusable content."""


class StoryProposalNotFoundError(StoryError):
    """A pending Story change proposal does not exist in the repository."""


class PersistenceError(Exception):
    """Raised when durable state cannot be read or written safely."""


class DocumentNotFoundError(Exception):
    """A requested source document or immutable version does not exist."""


class UnsupportedDocumentError(Exception):
    """An uploaded file is unsafe, too large, or has an unsupported type."""


class DocumentExtractionError(Exception):
    """A supported document could not produce usable plain text."""


class DocumentStorageError(Exception):
    """Document bytes could not be stored or retrieved safely."""


class DocumentVersionConflictError(Exception):
    """A document mutation used stale metadata."""


class DocumentExtractionBusyError(Exception):
    """The bounded extraction facility has no execution or waiting capacity."""


class DocumentExtractionTimeoutError(Exception):
    """Document extraction exceeded its configured subprocess deadline."""


class DocumentContextTooLargeError(Exception):
    """Selected document context exceeds the configured analysis window."""


class StoryQualityEvaluationError(Exception):
    """A semantic INVEST evaluator failed or returned unusable content."""


class StoryQualitySnapshotNotFoundError(Exception):
    """No persisted Story quality snapshot exists for a Feature."""


class StoryQualitySnapshotConflictError(Exception):
    """Stories changed before a quality snapshot could be committed."""


class ArchitectureMappingConflictError(Exception):
    """The current breakdown is not ready for architecture mapping."""


class BreakdownReviewNotFoundError(Exception):
    """No generated breakdown review exists for the Requirement."""


class BreakdownReviewStaleError(Exception):
    """A review mutation targeted evidence that has since changed."""


class ReviewFlagNotFoundError(Exception):
    """A requested flag is absent from the current review."""


class ApprovalWorkflowNotReadyError(Exception):
    """The breakdown is incomplete or lacks current attributed approvals."""


class ApprovalPolicyBlockedError(Exception):
    """The configured governance policy prevents final approval."""


class AuthenticationRequiredError(Exception):
    """A request did not carry a valid authenticated identity."""


class IdentityProviderUnavailableError(Exception):
    """The configured identity provider could not validate a request."""


class ActorNotFoundError(Exception):
    """An assignment target is not known to this workspace."""


class AiJobNotFoundError(Exception):
    """A requested durable AI job does not exist."""


class NotificationNotFoundError(Exception):
    """A requested actor notification does not exist."""


class SavedViewNotFoundError(Exception):
    """A requested saved worklist view is absent or belongs to another actor."""


class SavedViewConflictError(Exception):
    """A saved-view name or optimistic version conflicts with current state."""


class InvalidSavedViewError(Exception):
    """Saved-view content violates the reusable-view contract."""


class InvalidReportingWindowError(Exception):
    """The requested operational reporting window is unsupported."""


class BreakdownRevisionNotExportableError(Exception):
    """The selected immutable revision lacks a formal final approval."""


class BacklogExportFormatError(Exception):
    """A neutral export format cannot represent the selected content safely."""


class KnowledgeFindingNotFoundError(Exception):
    """A requested requirement-knowledge finding does not exist."""


class ModelTransportError(Exception):
    """Safe provider failure classification independent of transport libraries."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        messages = {
            "timeout": "The model request timed out. Retry after checking model performance.",
            "rate_limit": "The model provider rate limit was reached. Wait before retrying.",
            "authentication": (
                "The model provider rejected its credentials. Check backend configuration."
            ),
            "configuration": "The provider rejected the configured model or request parameters.",
            "index_required": (
                "Knowledge search needs a current index for the configured "
                "embedding model. Contact your administrator."
            ),
            "invalid_output": (
                "The model returned invalid, empty, refused or truncated structured output."
            ),
            "payment": (
                "The model provider requires available credits or a higher key spending limit."
            ),
            "invalid_citations": (
                "The model could not provide valid source citations. Analysis was not saved."
            ),
            "unavailable": "The model provider is currently unavailable. Try again later.",
        }
        super().__init__(messages.get(kind, messages["unavailable"]))


class KnowledgeIndexPendingError(Exception):
    """Derived Requirement knowledge has not caught up to its source changes."""


class KnowledgeGenerationError(Exception):
    """A knowledge provider failed or returned unusable evidence."""


class KnowledgeScreenConflictError(Exception):
    """Knowledge screening targeted content that has since changed."""


class AnswerSuggestionNotFoundError(Exception):
    """A referenced answer suggestion is absent or stale."""
