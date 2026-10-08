"""Domain errors for requirement knowledge screening (ADR-0103 PR 15a; split from `errors.py`)."""

from smb_requirement_agent.domain.knowledge.errors import KnowledgeError


class KnowledgeFindingConflictError(KnowledgeError):
    """A finding decision targeted stale or incompatible state."""


class KnowledgeReviewRequiredError(KnowledgeError):
    """Current requirement knowledge has not been screened and resolved."""


class RequirementRetiredError(KnowledgeError):
    """The Requirement is retired from the knowledge corpus, so it is not screened."""


class CorpusMembershipConflictError(KnowledgeError):
    """A retirement or reinstatement does not fit the Requirement's corpus membership."""
