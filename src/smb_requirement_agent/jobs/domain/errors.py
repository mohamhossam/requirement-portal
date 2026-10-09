"""AI job lifecycle errors."""


class AiJobError(Exception):
    """Base error for durable AI jobs."""


class InvalidAiJobError(AiJobError):
    """A job value or lifecycle transition is invalid."""


class AiJobConflictError(AiJobError):
    """A job mutation conflicts with its current state or idempotency key."""
