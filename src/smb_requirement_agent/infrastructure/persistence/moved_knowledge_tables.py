"""Drop the knowledge tables this database still holds, once nothing would be lost (ADR-0099).

The knowledge service owns the library, the architecture and squad catalogues
and their blobs. This database keeps the tables because earlier migrations
create them and `knowledge-import` reads them. Requirement work no longer reads
or writes any of them.

A table is dropped only when that loses nothing: it is empty, or the knowledge
database holds an identical copy (same row count and content checksum). One
table that fails the check refuses the whole drop, and nothing changes. The
check and the drop run in one transaction with the tables locked, so no row can
arrive in between. Tables already gone are skipped, so running again is safe.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import psycopg
from psycopg import sql

from smb_requirement_agent.application.errors import PersistenceError

# The tables `knowledge-portal import` copies, parents before children.
MOVED_TABLES: tuple[str, ...] = (
    "library_documents",
    "library_submissions",
    "library_chunks",
    "library_embedding_cache",
    "knowledge_document_blobs",
    "architecture_knowledge_releases",
    "architecture_knowledge_documents",
    "architecture_knowledge_indexes",
    "architecture_knowledge_chunks",
    "architecture_embedding_cache",
    "architecture_knowledge_audit",
    "architecture_catalogue_candidates",
    "architecture_extraction_runs",
    "architecture_sample_requirements",
    "architecture_jobs",
    "organisation_catalogue",
    "organisation_audit",
    "knowledge_events",
)


class TableState(StrEnum):
    ABSENT = "already gone"
    EMPTY = "empty"
    COPIED = "copied to the knowledge database"
    NOT_CHECKED = "holds rows, and no knowledge database was given to check them against"
    NOT_COPIED = "holds rows the knowledge database does not have"
    DIFFERS = "holds rows that differ from the knowledge database's copy"


DROPPABLE = frozenset({TableState.EMPTY, TableState.COPIED})


@dataclass(frozen=True)
class Fingerprint:
    rows: int
    checksum: str


@dataclass(frozen=True)
class TableReport:
    table: str
    state: TableState
    rows: int = 0


@dataclass(frozen=True)
class DropResult:
    reports: tuple[TableReport, ...]
    dropped: bool

    @property
    def refused(self) -> tuple[TableReport, ...]:
        return tuple(
            report
            for report in self.reports
            if report.state is not TableState.ABSENT and report.state not in DROPPABLE
        )


def decide(own: Fingerprint | None, copy: Fingerprint | None, *, checked: bool) -> TableState:
    """What one table's contents allow, given its copy in the knowledge database."""
    if own is None:
        return TableState.ABSENT
    if own.rows == 0:
        return TableState.EMPTY
    if not checked:
        return TableState.NOT_CHECKED
    if copy is None:
        return TableState.NOT_COPIED
    return TableState.COPIED if copy == own else TableState.DIFFERS


def drop_moved_tables(
    database_url: str,
    knowledge_database_url: str | None = None,
    *,
    dry_run: bool = False,
) -> DropResult:
    """Check every moved table, then drop them all or none."""
    with psycopg.connect(database_url) as connection:
        with connection.transaction():
            schema = _schema(connection)
            present = [table for table in MOVED_TABLES if _exists(connection, schema, table)]
            for table in reversed(present):
                connection.execute(
                    sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(
                        sql.Identifier(schema, table)
                    )
                )
            own = {table: _fingerprint(connection, schema, table) for table in present}
            copies = _copies(knowledge_database_url, [t for t in present if own[t].rows])
            reports = tuple(
                TableReport(
                    table,
                    decide(
                        own.get(table),
                        copies.get(table),
                        checked=knowledge_database_url is not None,
                    ),
                    own[table].rows if table in own else 0,
                )
                for table in MOVED_TABLES
            )
            result = DropResult(reports, dropped=False)
            if result.refused or dry_run:
                return result
            # Children first. No CASCADE: an unexpected dependent fails the drop
            # instead of being removed with it.
            for table in reversed(present):
                connection.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(schema, table)))
            return DropResult(reports, dropped=True)


def _copies(knowledge_database_url: str | None, tables: Sequence[str]) -> dict[str, Fingerprint]:
    if knowledge_database_url is None or not tables:
        return {}
    with psycopg.connect(knowledge_database_url) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            schema = _schema(connection)
            return {
                table: _fingerprint(connection, schema, table)
                for table in tables
                if _exists(connection, schema, table)
            }


# Every lookup is pinned to the connection's own schema, never found further
# along the search path, so a table elsewhere is neither measured nor dropped.
def _schema(connection: psycopg.Connection[tuple[object, ...]]) -> str:
    row = connection.execute("SELECT current_schema()").fetchone()
    if row is None or not isinstance(row[0], str):
        raise PersistenceError("The database reported no current schema.")
    return row[0]


def _exists(connection: psycopg.Connection[tuple[object, ...]], schema: str, table: str) -> bool:
    row = connection.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = %s AND tablename = %s)",
        (schema, table),
    ).fetchone()
    return bool(row and row[0])


def _fingerprint(
    connection: psycopg.Connection[tuple[object, ...]], schema: str, table: str
) -> Fingerprint:
    # Row order does not matter: rows are hashed sorted by their text form.
    row = connection.execute(
        sql.SQL(
            "SELECT count(*), md5(coalesce(string_agg(t::text, E'\\n' ORDER BY t::text), '')) "
            "FROM {} AS t"
        ).format(sql.Identifier(schema, table))
    ).fetchone()
    if row is None or not isinstance(row[0], int) or not isinstance(row[1], str):
        raise PersistenceError(f"Could not measure {table}.")
    return Fingerprint(row[0], row[1])
