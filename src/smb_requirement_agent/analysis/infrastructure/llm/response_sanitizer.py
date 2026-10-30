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


def clean_typed_statements(
    pairs: Iterable[tuple[str, str]], kinds: frozenset[str], fallback: str
) -> list[tuple[str, str]]:
    """Strip typed statements, drop the blank ones, and replace an unknown kind by `fallback`.

    The first of two statements that differ only in case or spacing is kept: they would share
    one citation key.
    """
    seen: set[str] = set()
    cleaned: list[tuple[str, str]] = []
    for statement, kind in pairs:
        text = statement.strip()
        key = " ".join(text.casefold().split())
        if not text or key in seen:
            continue
        seen.add(key)
        kind = kind.strip().casefold()
        cleaned.append((text, kind if kind in kinds else fallback))
    return cleaned


def clean_use_cases(items: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """Strip every field of a use case; drop one without a name, actor, goal or step.

    Use cases that differ only in the case or spacing of their name are one use case.
    """
    seen: set[str] = set()
    cleaned: list[dict[str, object]] = []
    for item in items:
        name = str(item.get("name") or "").strip()
        actor = str(item.get("actor") or "").strip()
        goal = str(item.get("goal") or "").strip()
        steps = clean_statements(str(step) for step in _strings(item.get("main_steps")))
        key = " ".join(name.casefold().split())
        if not name or not actor or not goal or not steps or key in seen:
            continue
        seen.add(key)
        trigger = str(item.get("trigger") or "").strip() or None
        cleaned.append(
            {
                "name": name,
                "actor": actor,
                "trigger": trigger,
                "goal": goal,
                "main_steps": steps,
                "alternate_paths": clean_statements(
                    str(step) for step in _strings(item.get("alternate_paths"))
                ),
                "business_rules": clean_statements(
                    str(rule) for rule in _strings(item.get("business_rules"))
                ),
            }
        )
    return cleaned


def _strings(value: object) -> list[object]:
    return list(value) if isinstance(value, list | tuple) else []
