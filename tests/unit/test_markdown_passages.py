"""Markdown passages follow headings and tables, so each table row keeps its header.

The reported failure: a Markdown landscape cut into 40-line windows split tables
from their headers and never told the model which section a row belonged to.
"""

from __future__ import annotations

from pathlib import Path

from smb_requirement_agent.infrastructure.architecture.markdown_passages import (
    MAX_PASSAGE_LINES,
    markdown_passages,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "catalogue" / "synthetic_landscape.md"


def _read(text: str) -> list[tuple[str, str, tuple[str, ...], bool]]:
    return [
        (item.location, item.text, item.heading_path, item.heading)
        for item in markdown_passages(text)
    ]


def test_headings_set_the_path_of_what_follows() -> None:
    text = "# Landscape\n\nIntro text.\n\n## Customer\n\nCare systems.\n\n### Assisted\n\nAgents.\n"

    assert _read(text) == [
        ("line 1", "Landscape", (), True),
        ("line 3", "Intro text.", ("Landscape",), False),
        ("line 5", "Customer", ("Landscape",), True),
        ("line 7", "Care systems.", ("Landscape", "Customer"), False),
        ("line 9", "Assisted", ("Landscape", "Customer"), True),
        ("line 11", "Agents.", ("Landscape", "Customer", "Assisted"), False),
    ]


def test_a_shallower_heading_closes_the_deeper_ones_and_setext_headings_count() -> None:
    text = "Landscape\n=========\n\n### Deep\n\nA.\n\nSecond\n------\n\nB.\n"

    assert [(location, path, heading) for location, _, path, heading in _read(text)] == [
        ("line 1", (), True),
        ("line 4", ("Landscape",), True),
        ("line 6", ("Landscape", "Deep"), False),
        ("line 8", ("Landscape",), True),
        ("line 11", ("Landscape", "Second"), False),
    ]


def test_sibling_headings_stay_siblings_when_a_document_starts_below_the_top_level() -> None:
    """A document opening at "##" once nested each "###" inside the one before it."""
    text = "## Product: Office\n\n### Proposition\n\nA line.\n\n### Order types\n\nB line.\n"

    assert [(body, path) for _, body, path, heading in _read(text) if not heading] == [
        ("A line.", ("Product: Office", "Proposition")),
        ("B line.", ("Product: Office", "Order types")),
    ]


def test_each_table_row_is_one_passage_that_repeats_its_header() -> None:
    text = (
        "## Systems\n"
        "\n"
        "| System | ID | Owner | Integrations | Aliases |\n"
        "|---|:---:|---|---|---|\n"
        "| 📈 BCRM | SYS-BCRM | Sales | CBCM, GIS | — |\n"
        "| Order \\| Hub | SYS-OH |  | BCRM | OH |\n"
    )

    rows = [(location, body) for location, body, _, heading in _read(text) if not heading]

    assert rows == [
        ("line 5", "System: 📈 BCRM | ID: SYS-BCRM | Owner: Sales | Integrations: CBCM, GIS"),
        ("line 6", "System: Order | Hub | ID: SYS-OH | Integrations: BCRM | Aliases: OH"),
    ]
    assert all(path == ("Systems",) for _, _, path, heading in _read(text) if not heading)


def test_a_line_with_pipes_and_no_delimiter_row_is_a_paragraph() -> None:
    assert _read("Use A | B when needed.\nThen C.\n") == [
        ("lines 1-2", "Use A | B when needed.\nThen C.", (), False)
    ]


def test_lists_quotes_and_fences_are_passages_and_fences_hide_headings() -> None:
    text = "- one\n- two\n\n> quoted\n\n```mermaid\n# not a heading\nA --> B\n```\n\n---\n\nTail.\n"

    assert [
        (location, body.splitlines()[0], heading) for location, body, _, heading in _read(text)
    ] == [
        ("lines 1-2", "- one", False),
        ("line 4", "> quoted", False),
        ("lines 6-9", "```mermaid", False),
        ("line 13", "Tail.", False),
    ]


def test_long_blocks_are_cut_into_bounded_passages() -> None:
    text = "\n".join(f"word {n}" for n in range(1, MAX_PASSAGE_LINES + 6))

    assert [location for location, *_ in _read(text)] == [
        f"lines 1-{MAX_PASSAGE_LINES}",
        f"lines {MAX_PASSAGE_LINES + 1}-{MAX_PASSAGE_LINES + 5}",
    ]


def test_front_matter_is_one_passage_and_windows_line_endings_are_read() -> None:
    text = "---\r\ntitle: Landscape\r\n---\r\n# Systems\r\n\r\nBody.\r\n"

    assert _read(text) == [
        ("lines 1-3", "---\ntitle: Landscape\n---", (), False),
        ("line 4", "Systems", (), True),
        ("line 6", "Body.", ("Systems",), False),
    ]


def test_a_landscape_document_reads_into_sectioned_rows() -> None:
    passages = markdown_passages(FIXTURE.read_text(encoding="utf-8"))
    rows = [item for item in passages if item.text.startswith("System: ")]

    assert len(rows) == 6
    assert rows[0].heading_path == ("Synthetic Landscape", "Systems", "Ordering (TAM · Ordering)")
    assert rows[0].text.startswith("System: 🛒 Order Portal | ID: SYS-PORTAL")
    # Every passage is the document's own text, so a quote from it can be checked.
    source = FIXTURE.read_text(encoding="utf-8")
    assert all(item.text.split(" | ")[0].split(": ", 1)[-1] in source for item in rows)
