"""AI job lifecycle errors."""


class AiJobError(Exception):
    """Base error for durable AI jobs."""


class InvalidAiJobError(AiJobError):
    """A job value or lifecycle transition is invalid."""


class AiJobConflictError(AiJobError):
    """A job mutation conflicts with its current state or idempotency key."""


class AiJobInputsPrunedError(AiJobError):
    """The job's stored inputs were pruned by retention (ADR-0079), so it cannot be retried."""
