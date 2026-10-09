"""A moved knowledge table is dropped only when that loses nothing (ADR-0099)."""

from __future__ import annotations

import re

import pytest

from smb_requirement_agent.infrastructure.persistence.migration_runner import MIGRATIONS
from smb_requirement_agent.infrastructure.persistence.moved_knowledge_tables import (
    DROP_EMPTY_MIGRATION,
    MOVED_TABLES,
    DropResult,
    Fingerprint,
    TableReport,
    TableState,
    decide,
)
from smb_requirement_agent.interfaces.drop_knowledge_tables import _summary

ROWS = Fingerprint(3, "abc")


@pytest.mark.parametrize(
    ("own", "copy", "checked", "state"),
    [
        (None, None, True, TableState.ABSENT),
        (Fingerprint(0, "e"), None, False, TableState.EMPTY),
        (ROWS, None, False, TableState.NOT_CHECKED),
        (ROWS, None, True, TableState.NOT_COPIED),
        (ROWS, Fingerprint(3, "abc"), True, TableState.COPIED),
        (ROWS, Fingerprint(3, "abd"), True, TableState.DIFFERS),
        (ROWS, Fingerprint(2, "abc"), True, TableState.DIFFERS),
    ],
)
def test_each_table_is_judged_by_what_dropping_it_would_lose(
    own: Fingerprint | None, copy: Fingerprint | None, checked: bool, state: TableState
) -> None:
    assert decide(own, copy, checked=checked) is state


def test_the_tables_are_the_ones_the_knowledge_import_copies() -> None:
    assert len(MOVED_TABLES) == len(set(MOVED_TABLES)) == 18
    # Parents before children; the drop runs in reverse.
    assert MOVED_TABLES.index("library_documents") < MOVED_TABLES.index("library_chunks")
    assert MOVED_TABLES.index("architecture_knowledge_releases") < MOVED_TABLES.index(
        "architecture_knowledge_chunks"
    )


def test_the_migration_drops_the_same_tables_children_first() -> None:
    text = (MIGRATIONS / DROP_EMPTY_MIGRATION).read_text(encoding="utf-8")
    listed = text.split("ARRAY[", 1)[1].split("]", 1)[0]
    assert tuple(re.findall(r"'([a-z_]+)'", listed)) == tuple(reversed(MOVED_TABLES))


def test_one_table_that_would_lose_rows_refuses_the_whole_drop() -> None:
    result = DropResult(
        (
            TableReport("library_documents", TableState.EMPTY),
            TableReport("organisation_catalogue", TableState.NOT_CHECKED, 1),
            TableReport("knowledge_events", TableState.ABSENT),
        ),
        dropped=False,
    )

    assert [report.table for report in result.refused] == ["organisation_catalogue"]
    assert _summary(result, dry_run=False).splitlines() == [
        "library_documents: empty",
        "organisation_catalogue: holds rows, and no knowledge database was given to check them "
        "against (1 rows)",
        "knowledge_events: already gone",
        "Refused: 1 of 2 tables would lose rows.",
    ]


def test_the_summary_says_what_was_dropped_or_would_be() -> None:
    reports = (
        TableReport("library_documents", TableState.EMPTY),
        TableReport("organisation_catalogue", TableState.COPIED, 1),
    )
    assert _summary(DropResult(reports, dropped=True), dry_run=False).endswith("Dropped 2 tables.")
    assert _summary(DropResult(reports, dropped=False), dry_run=True).endswith(
        "Dry run: 2 tables would be dropped."
    )
    gone = (TableReport("library_documents", TableState.ABSENT),)
    assert _summary(DropResult(gone, dropped=False), dry_run=False).endswith("Nothing to drop.")
