"""Durable-job, notification and rate-limit failures raised by the jobs use cases."""


class ProviderRateLimitExceededError(Exception):
    """An actor started more provider-calling operations than the rate limit allows."""

    def __init__(self, message: str, retry_after_seconds: int = 60) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ProviderBudgetExhaustedError(Exception):
    """The day's provider token budget is spent; new AI work waits for the next UTC day."""

    def __init__(self, message: str, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class AiJobNotFoundError(Exception):
    """A requested durable AI job does not exist."""


class NotificationNotFoundError(Exception):
    """A requested actor notification does not exist."""
