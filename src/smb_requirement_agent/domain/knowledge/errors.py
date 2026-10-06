"""Domain errors for requirement knowledge review."""


class KnowledgeError(Exception):
    """Base error for knowledge-review behavior."""


class InvalidKnowledgeError(KnowledgeError):
    """Knowledge content violates a domain invariant."""


class KnowledgeFindingConflictError(KnowledgeError):
    """A finding decision targeted stale or incompatible state."""


class KnowledgeReviewRequiredError(KnowledgeError):
    """Current requirement knowledge has not been screened and resolved."""


class RequirementRetiredError(KnowledgeError):
    """The Requirement is retired from the knowledge corpus, so it is not screened."""


class CorpusMembershipConflictError(KnowledgeError):
    """A retirement or reinstatement does not fit the Requirement's corpus membership."""
