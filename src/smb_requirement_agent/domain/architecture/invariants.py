"""What every part of the architecture catalogue refuses, shared without import cycles."""

from __future__ import annotations


class InvalidKnowledgeError(ValueError):
    """A proposed catalogue violates a business invariant."""


def required(value: str, label: str) -> str:
    """The value trimmed, or InvalidKnowledgeError when nothing is left."""
    result = value.strip()
    if not result:
        raise InvalidKnowledgeError(f"{label} must not be blank.")
    return result


def optional(value: str | None, label: str) -> str | None:
    """Like ``required`` when a value is given; None stays None."""
    return None if value is None else required(value, label)
