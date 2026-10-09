"""Requirement work holds no knowledge rows (ADR-0099; the platform split's Stage 5).

The library, the catalogues, their blobs and the event outbox belong to the knowledge
service. Requirement code reaches them only through its ports, over HTTP. Earlier
migrations still create the tables here, and the last two drop them again; no code may
name one, so no requirement transaction reads, writes or locks a knowledge row.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.knowledge_tables import KNOWLEDGE_TABLES

SOURCE = Path(__file__).resolve().parents[2] / "src" / "smb_requirement_agent"
NAMED = re.compile(r"\b(" + "|".join(KNOWLEDGE_TABLES) + r")\b")


def _named_tables(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        f"{path.relative_to(SOURCE)}:{node.lineno} names {found.group(0)}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and (found := NAMED.search(node.value))
    ]


def test_no_requirement_code_names_a_knowledge_table() -> None:
    # Migrations are SQL files, so they are not read here.
    found = [line for path in sorted(SOURCE.rglob("*.py")) for line in _named_tables(path)]

    assert found == []


def test_the_check_would_see_a_table_named_in_sql() -> None:
    sample = 'connection.execute("SELECT payload FROM library_documents FOR SHARE")'
    tree = ast.parse(sample)

    assert any(
        isinstance(node, ast.Constant) and isinstance(node.value, str) and NAMED.search(node.value)
        for node in ast.walk(tree)
    )
