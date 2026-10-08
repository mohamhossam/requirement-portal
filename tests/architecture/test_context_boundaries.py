"""Bounded-context rules import-linter cannot express (ADR-0103).

import-linter checks which modules import which. These tests check where certain calls are
made (who subscribes domain-event handlers, and who builds the dispatcher) and the package
layout itself.
"""

from __future__ import annotations

import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "src" / "smb_requirement_agent"
SUBSCRIPTIONS = SOURCE / "interfaces" / "api" / "composition" / "events.py"


def _calls(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)]


def _sources() -> list[Path]:
    return sorted(SOURCE.rglob("*.py"))


def test_event_handlers_are_subscribed_only_in_the_composition_root() -> None:
    offenders = [
        f"{path.relative_to(SOURCE)}:{call.lineno}"
        for path in _sources()
        if path != SUBSCRIPTIONS
        for call in _calls(path)
        if isinstance(call.func, ast.Attribute) and call.func.attr == "subscribe"
    ]

    assert offenders == [], (
        "Domain-event handlers are subscribed only in interfaces/api/composition/events.py "
        f"(ADR-0103 §3): {offenders}"
    )


def test_the_dispatcher_is_built_only_by_the_composition_root() -> None:
    interfaces = SOURCE / "interfaces" / "api"
    offenders = [
        f"{path.relative_to(SOURCE)}:{call.lineno}"
        for path in _sources()
        if path != interfaces / "container.py" and interfaces / "composition" not in path.parents
        for call in _calls(path)
        if isinstance(call.func, ast.Name) and call.func.id == "InProcessEventDispatcher"
    ]

    assert offenders == [], (
        "InProcessEventDispatcher is constructed only in the composition root "
        f"(AGENTS.md §4.4.1): {offenders}"
    )


# Each context's layers (ADR-0103 §1, Amendment 2): reporting reads projections and has no
# domain; workflows orchestrates the other contexts.
CONTEXT_LAYERS = {
    "identity": {"domain", "application", "infrastructure"},
    "jobs": {"domain", "application", "infrastructure"},
    "requirements": {"domain", "application", "infrastructure"},
    "references": {"domain", "application", "infrastructure"},
    "analysis": {"domain", "application", "infrastructure"},
    "knowledge": {"domain", "application", "infrastructure"},
    "breakdown": {"domain", "application", "infrastructure"},
    "governance": {"domain", "application", "infrastructure"},
    "reporting": {"application", "infrastructure"},
    "workflows": {"application", "infrastructure"},
}


def _packages(directory: Path) -> set[str]:
    return {child.name for child in directory.iterdir() if (child / "__init__.py").is_file()}


def test_every_context_has_exactly_its_layers() -> None:
    layers = {context: _packages(SOURCE / context) for context in CONTEXT_LAYERS}

    assert layers == CONTEXT_LAYERS


def test_the_layer_first_packages_stay_gone() -> None:
    """The contexts replaced the top-level domain/ and application/use_cases/ (PR 16)."""
    assert "domain" not in _packages(SOURCE)
    assert "use_cases" not in _packages(SOURCE / "application")


def test_no_migration_shims_remain() -> None:
    tests = SOURCE.parents[1] / "tests"
    marker = "MIGRATION" + " SHIM"  # Split so this file does not match itself.
    offenders = [
        str(path)
        for path in (*_sources(), *sorted(tests.rglob("*.py")))
        if marker in path.read_text(encoding="utf-8")
    ]

    assert offenders == [], f"Import from the context package instead: {offenders}"
