"""Application failures caused by orchestration or external boundaries.

Infrastructure failures raised by platform-kernel mechanisms are re-exported, not
redefined (ADR-0100), so a handler for one of these names catches exactly what
the kernel raises.
"""

from smb_kernel.errors import AuthenticationRequiredError as AuthenticationRequiredError
from smb_kernel.errors import DocumentExtractionBusyError as DocumentExtractionBusyError
from smb_kernel.errors import DocumentExtractionError as DocumentExtractionError
from smb_kernel.errors import DocumentExtractionTimeoutError as DocumentExtractionTimeoutError
from smb_kernel.errors import IdentityProviderUnavailableError as IdentityProviderUnavailableError
from smb_kernel.errors import KnowledgeGenerationError as KnowledgeGenerationError
from smb_kernel.errors import ModelTransportError as ModelTransportError
from smb_kernel.errors import PersistenceError as PersistenceError
from smb_kernel.errors import UnsupportedDocumentError as UnsupportedDocumentError

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


class DocumentNotFoundError(Exception):
    """A requested source document or immutable version does not exist."""


class DocumentStorageError(Exception):
    """Document bytes could not be stored or retrieved safely."""


class DocumentVersionConflictError(Exception):
    """A document mutation used stale metadata."""


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


class KnowledgeIndexPendingError(Exception):
    """Derived Requirement knowledge has not caught up to its source changes."""


class KnowledgeScreenConflictError(Exception):
    """Knowledge screening targeted content that has since changed."""


class AnswerSuggestionNotFoundError(Exception):
    """A referenced answer suggestion is absent or stale."""
