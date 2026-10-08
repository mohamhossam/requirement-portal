"""Requirement and source-document failures raised by the requirements use cases."""

from smb_requirement_agent.requirements.domain.requirement.errors import RequirementError


class RequirementNotFoundError(RequirementError):
    """A requested Requirement does not exist in the repository."""


class DuplicateRequirementError(RequirementError):
    """A repository already contains the requested Requirement identity."""


class RequirementDraftNotFoundError(RequirementError):
    """A requested resumable draft does not exist."""


class RequirementVersionConflictError(RequirementError):
    """An optimistic source edit used a stale version."""


class RequirementImpactAcknowledgementRequiredError(RequirementError):
    """A source edit would invalidate generated content without acknowledgement."""


class RequirementAnalysisIneligibleError(RequirementError):
    """A Requirement is missing source fields required for analysis."""


class DocumentNotFoundError(Exception):
    """A requested source document or immutable version does not exist."""


class DocumentStorageError(Exception):
    """Document bytes could not be stored or retrieved safely."""


class DocumentVersionConflictError(Exception):
    """A document mutation used stale metadata."""
