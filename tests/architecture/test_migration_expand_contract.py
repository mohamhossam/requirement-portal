"""Migrations expand by default; a contract step says so (ADR-0108).

A release runs its migrations before its new processes start, while the previous
release's processes may still be serving, and rolling back means redeploying the
previous release's images onto the migrated database. Both work only when a
migration adds without taking away. Dropping, renaming or retyping a table or
column, or emptying a table, breaks the release before it. Such a change is a
contract step: it ships only after no running release reads the old shape, and its
file says so with a `-- contract-step: <why it is safe now>` line.

Statements built at run time (`EXECUTE` inside `DO`) are scanned too, because the
words are in their string literals.
"""

import re

import pytest

from smb_requirement_agent.infrastructure.persistence.migration_runner import MIGRATIONS

# Written before this rule; 202610091000/202610091200 retire the knowledge tables
# (ADR-0104) and are contract steps in all but name.
GRANDFATHERED_THROUGH = "202610091200"
TIMESTAMPED = re.compile(r"^(\d{12})_")
CONTRACT_MARKER = re.compile(r"^[ \t]*--[ \t]*contract-step:[ \t]*\S", re.I | re.M)
COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
CONTRACTING = {
    "drop": re.compile(
        r"\bdrop\s+(?!default\b|not\s+null\b|identity\b|expression\b)"
        r"(?:table|column|index|constraint|view|materialized|type|schema|function|"
        r"trigger|sequence|extension|policy|rule|domain|\w+)\b",
        re.I,
    ),
    "rename": re.compile(r"\brename\b", re.I),
    "retype": re.compile(r"\balter\s+column\s+\S+\s+(?:set\s+data\s+)?type\b", re.I),
    "truncate": re.compile(r"\btruncate\b", re.I),
}


def contracting_changes(sql: str) -> list[str]:
    """The kinds of contracting change in a migration, unless it is marked as one."""
    if CONTRACT_MARKER.search(sql):
        return []
    code = COMMENTS.sub(" ", sql)
    return [kind for kind, pattern in CONTRACTING.items() if pattern.search(code)]


def _checked_migrations() -> list[str]:
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    return [
        name
        for name in names
        if (match := TIMESTAMPED.match(name)) and match.group(1) > GRANDFATHERED_THROUGH
    ]


def test_migrations_after_the_cutoff_were_found() -> None:
    assert _checked_migrations(), "No migration is newer than the grandfathered set."


def test_every_new_migration_only_expands_unless_marked_a_contract_step() -> None:
    contracting = {
        name: kinds
        for name in _checked_migrations()
        if (kinds := contracting_changes((MIGRATIONS / name).read_text(encoding="utf-8")))
    }

    assert not contracting, (
        f"These migrations contract the schema: {contracting}. Make the change additive, "
        "or ship it as a contract step with a '-- contract-step: <why it is safe now>' line "
        "(WORKSPACE.md, 'Migrations')."
    )


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz;", []),
        ("CREATE INDEX IF NOT EXISTS jobs_idx ON jobs (requirement_id);", []),
        ("ALTER TABLE jobs ALTER COLUMN note DROP NOT NULL;", []),
        ("ALTER TABLE jobs ALTER COLUMN note DROP DEFAULT;", []),
        ("-- Nothing is dropped here.\nSELECT 1;", []),
        ("DROP TABLE IF EXISTS old_jobs;", ["drop"]),
        ("ALTER TABLE jobs DROP COLUMN note;", ["drop"]),
        ("DROP INDEX jobs_idx;", ["drop"]),
        ("ALTER TABLE jobs RENAME COLUMN note TO notes;", ["rename"]),
        ("ALTER TABLE jobs ALTER COLUMN attempts TYPE bigint;", ["retype"]),
        ("ALTER TABLE jobs ALTER COLUMN attempts SET DATA TYPE bigint;", ["retype"]),
        ("TRUNCATE jobs;", ["truncate"]),
        (
            "DO $$ BEGIN EXECUTE format('DROP TABLE %I', 'old_jobs'); END $$;",
            ["drop"],
        ),
        (
            "-- contract-step: no release since v0.3.0 reads note\n"
            "ALTER TABLE jobs DROP COLUMN note;",
            [],
        ),
        ("-- contract-step:\nALTER TABLE jobs DROP COLUMN note;", ["drop"]),
    ],
)
def test_the_scan_tells_expanding_from_contracting_changes(sql: str, expected: list[str]) -> None:
    assert contracting_changes(sql) == expected
