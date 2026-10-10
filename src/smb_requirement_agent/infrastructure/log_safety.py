"""What operational logs may say about an exception: its type, and its causes' types.

An exception's message can quote a document, a requirement or a provider's reply, so
operational logs never carry it. The opt-in debug trace keeps the detail.
"""

from __future__ import annotations

import traceback

_MAX_CAUSES = 5


def exception_types(exc: BaseException) -> str:
    """`OuterError <- CauseError <- ...`: the cause chain by type name, without messages."""
    names: list[str] = []
    current: BaseException | None = exc
    while current is not None and len(names) < _MAX_CAUSES:
        names.append(type(current).__name__)
        current = current.__cause__
    return " <- ".join(names)


def exception_frames(exc: BaseException) -> str:
    """Where `exc` was raised: file, line, function and source line, without its message."""
    return "".join(traceback.format_list(traceback.extract_tb(exc.__traceback__))).rstrip()
