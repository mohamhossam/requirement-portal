"""Offline command: drop the knowledge tables this database still holds (ADR-0099).

Run it once, after `knowledge-import` when moving an earlier system's data. A
fresh database needs nothing: its migrations drop the tables while all are
empty, and this then reports nothing to drop. It
drops every moved table or none: a table holding rows is dropped only when the
knowledge database (`--knowledge-database-url`) holds an identical copy.
`--dry-run` reports what would happen and changes nothing.
"""

import argparse

from smb_requirement_agent.infrastructure.config.options import PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import PersistenceSettings
from smb_requirement_agent.infrastructure.persistence.moved_knowledge_tables import (
    DROPPABLE,
    DropResult,
    TableState,
    drop_moved_tables,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Drop the library, catalogue and event tables the knowledge service now owns."
    )
    parser.add_argument(
        "--knowledge-database-url",
        help="The knowledge database, to check that tables holding rows were copied there.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Report what would be dropped; change nothing."
    )
    args = parser.parse_args()
    persistence = PersistenceSettings.from_env()
    if persistence.provider is not PersistenceProvider.POSTGRES or persistence.database_url is None:
        parser.error(
            "Dropping the knowledge tables requires PostgreSQL persistence and DATABASE_URL."
        )
    result = drop_moved_tables(
        persistence.database_url, args.knowledge_database_url, dry_run=args.dry_run
    )
    print(_summary(result, dry_run=args.dry_run))
    if result.refused:
        parser.exit(1, "Nothing was dropped.\n")


def _summary(result: DropResult, *, dry_run: bool) -> str:
    lines = []
    for report in result.reports:
        rows = f" ({report.rows} rows)" if report.rows else ""
        lines.append(f"{report.table}: {report.state.value}{rows}")
    present = [r for r in result.reports if r.state is not TableState.ABSENT]
    if result.refused:
        lines.append(f"Refused: {len(result.refused)} of {len(present)} tables would lose rows.")
    elif result.dropped:
        lines.append(f"Dropped {len(present)} tables.")
    elif dry_run and present:
        droppable = sum(r.state in DROPPABLE for r in present)
        lines.append(f"Dry run: {droppable} tables would be dropped.")
    else:
        lines.append("Nothing to drop.")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
