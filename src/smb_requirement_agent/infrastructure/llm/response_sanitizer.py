"""Normalisation of raw provider output into a valid analysis candidate.

The structured-output schema constrains the *shape* of a provider response but
not its content: a schema-valid response may still contain empty or
whitespace-only entries, which the analysis domain rejects.  Cleaning that up
is an adapter responsibility — the domain must never be handed content it
cannot accept, and the application layer must not learn that providers
misbehave.

Entries carrying no information are dropped.  A response with no usable content
at all is a failed generation, not an empty analysis.
"""

from __future__ import annotations

from collections.abc import Iterable

from smb_requirement_agent.analysis.application.errors import RequirementAnalysisGenerationError


def clean_statements(values: Iterable[str]) -> list[str]:
    """Strip each value and drop the ones left empty."""
    return [stripped for value in values if (stripped := value.strip())]


def clean_pairs(pairs: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """Strip both halves of each pair, dropping any pair missing either half."""
    cleaned = []
    for first, second in pairs:
        first, second = first.strip(), second.strip()
        if first and second:
            cleaned.append((first, second))
    return cleaned


def require_any_content(*groups: list[str] | list[tuple[str, str]]) -> None:
    """Raise if every category came back empty after cleaning."""
    if not any(groups):
        raise RequirementAnalysisGenerationError("Provider returned no usable analysis content.")
