"""User Story domain errors."""


class StoryError(Exception):
    """Base error for Story behavior."""


class InvalidStoryContentError(StoryError):
    """Human-authored Story content is invalid."""


class StoriesAlreadyExistError(StoryError):
    """Initial generation was attempted for a non-empty Story collection."""


class StoryRegenerationConflictError(StoryError):
    """Regeneration would replace human-owned Story content."""


class FeatureNotReadyForStoriesError(StoryError):
    """The parent Feature is not approved and current."""


class StoryProposalConflictError(StoryError):
    """A proposal no longer matches its source Stories."""
