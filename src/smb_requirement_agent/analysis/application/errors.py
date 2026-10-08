"""Analysis failures raised by the analysis use cases."""

from smb_requirement_agent.analysis.domain.errors import RequirementAnalysisError


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


class DocumentContextTooLargeError(Exception):
    """Selected document context exceeds the configured analysis window."""
