"""Domain errors for requirement knowledge review."""


class KnowledgeError(Exception):
    """Base error for knowledge-review behavior."""


class InvalidKnowledgeError(KnowledgeError):
    """Knowledge content violates a domain invariant."""


class KnowledgeFindingConflictError(KnowledgeError):
    """A finding decision targeted stale or incompatible state."""


class KnowledgeReviewRequiredError(KnowledgeError):
    """Current requirement knowledge has not been screened and resolved."""
