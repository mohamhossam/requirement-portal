"""Requirement-knowledge failures raised by the knowledge use cases."""


class KnowledgeFindingNotFoundError(Exception):
    """A requested requirement-knowledge finding does not exist."""


class KnowledgeIndexPendingError(Exception):
    """Derived Requirement knowledge has not caught up to its source changes."""


class KnowledgeScreenConflictError(Exception):
    """Knowledge screening targeted content that has since changed."""


class AnswerSuggestionNotFoundError(Exception):
    """A referenced answer suggestion is absent or stale."""
