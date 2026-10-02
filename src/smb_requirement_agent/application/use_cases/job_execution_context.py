"""Attempt identity scoped to one executor invocation, never discovered by Requirement."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from smb_requirement_agent.application.ports.ai_jobs import AiJobRecord

_attempt: ContextVar[AiJobRecord | None] = ContextVar("ai_execution_attempt", default=None)


def current_attempt() -> AiJobRecord | None:
    return _attempt.get()


@contextmanager
def bind_attempt(record: AiJobRecord) -> Iterator[None]:
    token = _attempt.set(record)
    try:
        yield
    finally:
        _attempt.reset(token)
