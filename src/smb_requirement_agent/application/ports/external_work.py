"""Commit preconditions attached to one explicit external-work scope."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_guards: ContextVar[tuple[Callable[[], None], ...]] = ContextVar(
    "external_resume_guards", default=()
)


@contextmanager
def guard_external_work(check: Callable[[], None]) -> Iterator[None]:
    token = _guards.set((*_guards.get(), check))
    try:
        yield
    finally:
        _guards.reset(token)


def check_external_result() -> None:
    """Called after transaction ownership resumes, before any generated writes."""
    for check in _guards.get():
        check()
