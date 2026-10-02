"""Source-level rules that keep production behaviour independent of interpreter flags."""

import ast
from pathlib import Path

import smb_requirement_agent

SOURCE_ROOT = Path(smb_requirement_agent.__file__).parent


def test_production_code_uses_explicit_errors_instead_of_assert() -> None:
    """`python -O` strips assert, which would silently remove these checks."""
    offenders = [
        f"{path.relative_to(SOURCE_ROOT)}:{node.lineno}"
        for path in sorted(SOURCE_ROOT.rglob("*.py"))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Assert)
    ]

    assert not offenders, "Raise an explicit error instead of assert: " + ", ".join(offenders)


# Modules whose imports must stay inside functions, and why.
DEFERRED_IMPORTS = {
    "infrastructure/documents/bounded_extractor.py": (
        "runs in the spawned extraction child, which must cap native thread pools "
        "before NumPy-backed extractors are imported"
    ),
    "infrastructure/documents/process_resources.py": (
        "imports the running platform's OS API only (resource on Unix, ctypes on Windows)"
    ),
}


def test_every_import_is_at_module_level() -> None:
    """A function-level import hides a dependency and usually papers over a cycle.

    Every dependency this package imports is installed, so none needs deferring;
    the two exceptions above are process- and platform-specific.
    """
    offenders: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        relative = path.relative_to(SOURCE_ROOT).as_posix()
        if relative in DEFERRED_IMPORTS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            offenders.extend(
                f"{relative}:{node.lineno}"
                for node in ast.walk(function)
                if isinstance(node, ast.ImportFrom | ast.Import)
            )

    assert not offenders, "Import at module level: " + ", ".join(offenders)


def test_deferred_import_exceptions_are_still_needed() -> None:
    for relative in DEFERRED_IMPORTS:
        tree = ast.parse((SOURCE_ROOT / relative).read_text(encoding="utf-8"))
        assert any(
            isinstance(node, ast.Import | ast.ImportFrom)
            for function in ast.walk(tree)
            if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef)
            for node in ast.walk(function)
        ), f"{relative} no longer defers an import; remove it from DEFERRED_IMPORTS."
