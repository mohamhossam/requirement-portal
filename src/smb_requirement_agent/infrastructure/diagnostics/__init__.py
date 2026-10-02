"""Opt-in local diagnostic tracing."""

from smb_requirement_agent.infrastructure.diagnostics.debug_trace import (
    DebugTrace,
    JsonLinesDebugTrace,
    NullDebugTrace,
    build_debug_trace,
)

__all__ = [
    "DebugTrace",
    "JsonLinesDebugTrace",
    "NullDebugTrace",
    "build_debug_trace",
]
