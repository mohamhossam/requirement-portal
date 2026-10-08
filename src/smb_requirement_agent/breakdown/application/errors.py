"""Epic, Feature, Story, quality and architecture-mapping failures raised by breakdown."""

from smb_requirement_agent.breakdown.domain.epic.errors import EpicError
from smb_requirement_agent.breakdown.domain.feature.errors import FeatureError
from smb_requirement_agent.breakdown.domain.story.errors import StoryError


class ArchitectureJobNotFoundError(Exception):
    """An architecture job does not exist."""


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


class StoryQualityEvaluationError(Exception):
    """A semantic INVEST evaluator failed or returned unusable content."""


class StoryQualitySnapshotNotFoundError(Exception):
    """No persisted Story quality snapshot exists for a Feature."""


class StoryQualitySnapshotConflictError(Exception):
    """Stories changed before a quality snapshot could be committed."""


class ArchitectureMappingConflictError(Exception):
    """The current breakdown is not ready for architecture mapping."""


class ArchitectureMappingProfileChangedError(Exception):
    """A queued mapping was asked for under models that are no longer configured.

    It reports as `architecture_knowledge_conflict`, as it did while mapping jobs
    ran in the catalogue's queue (ADR-0099).
    """
