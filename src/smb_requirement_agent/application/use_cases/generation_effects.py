"""Stage reusable generation effects until the owning mutation accepts its result."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_effects: ContextVar[list[Callable[[], None]] | None] = ContextVar(
    "generation_effects", default=None
)


def stage_generation_effect(write: Callable[[], None]) -> None:
    effects = _effects.get()
    if effects is not None:
        effects.append(write)


@contextmanager
def accepted_generation_effects() -> Iterator[None]:
    """Invoke inside the owner's transaction; discard on any rejected result."""
    existing = _effects.get()
    if existing is not None:
        yield
        return
    effects: list[Callable[[], None]] = []
    token = _effects.set(effects)
    try:
        yield
        for write in effects:
            write()
    finally:
        _effects.reset(token)
