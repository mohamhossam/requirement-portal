"""Requirement Analysis domain errors."""


class RequirementAnalysisError(Exception):
    """Base class for requirement analysis errors."""


class InvalidAnalysisContentError(RequirementAnalysisError):
    """Raised when an analysis field is empty or invalid."""


class InvalidClarificationError(RequirementAnalysisError):
    """Raised when human clarification input is empty or duplicated."""


class AnalysisClarificationConflictError(RequirementAnalysisError):
    """Raised when an answer no longer matches the current analysis."""


class AnalysisConfirmationBlockedError(RequirementAnalysisError):
    """Raised when a human tries to confirm an analysis with unresolved items."""


class InvalidClarificationTransitionError(RequirementAnalysisError):
    """Raised when a question mutation violates its lifecycle."""


class ClarificationVersionConflictError(RequirementAnalysisError):
    """Raised when a collaborator writes from stale question state."""


class IntentProposalVersionConflictError(RequirementAnalysisError):
    """Raised when an owner decides from stale intent-proposal state."""


class InvalidIntentProposalDecisionError(RequirementAnalysisError):
    """Raised when an intent-proposal decision is incomplete or invalid."""


class InvalidIntentProposalTransitionError(RequirementAnalysisError):
    """Raised when a confirmed analysis proposal is changed."""
