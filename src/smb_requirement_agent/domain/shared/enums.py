"""Mapping external strings onto domain enums.

Provider output and client input both arrive as strings that must become enum
members. The lookup is shared; the error is not. An unrecognised value from a
provider is a generation failure, while the same value from a caller is a bad
request, so each call site raises its own error rather than one being coerced
into the other.
"""

from __future__ import annotations

from enum import Enum


def value_of[T: Enum](enum_type: type[T], raw: str) -> T | None:
    """Return the member whose value matches `raw`, or None."""
    normalised = raw.strip().lower()
    for member in enum_type:
        if member.value == normalised:
            return member
    return None


def supported_values(enum_type: type[Enum]) -> str:
    """A sorted, comma-separated list of the enum's values, for error messages."""
    return ", ".join(sorted(member.value for member in enum_type))
