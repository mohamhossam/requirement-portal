"""Packaged migration catalogue invariants that readiness and deploys rely on."""

import re
from collections import Counter
from datetime import datetime

from smb_requirement_agent.infrastructure.persistence.migration_runner import (
    MIGRATIONS,
    latest_packaged_migration,
)

# Applied before this rule existed. Renaming either would make the runner apply
# it a second time on every database that already recorded the original name.
GRANDFATHERED_DUPLICATE_PREFIXES = {"018"}


def test_readiness_target_is_the_newest_packaged_migration() -> None:
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))

    assert latest_packaged_migration() == names[-1]


def test_migration_prefixes_are_unique_apart_from_grandfathered_history() -> None:
    prefixes = Counter(path.name.split("_", 1)[0] for path in MIGRATIONS.glob("*.sql"))
    duplicates = {prefix for prefix, count in prefixes.items() if count > 1}

    assert duplicates <= GRANDFATHERED_DUPLICATE_PREFIXES, (
        f"Duplicate migration prefixes {sorted(duplicates - GRANDFATHERED_DUPLICATE_PREFIXES)}: "
        "give the new migration the next unused number."
    )


# Sequential numbers collide when two branches each add "the next" migration;
# the last one ever issued is frozen here. New migrations are named by UTC
# timestamp (YYYYMMDDHHMM_description.sql), which sorts after every legacy
# number, so the runner's lexical order stays the order of creation.
LAST_SEQUENTIAL_MIGRATION = "026"
TIMESTAMPED_MIGRATION = re.compile(r"^(\d{12})_[a-z0-9]+(?:_[a-z0-9]+)*\.sql$")


def test_new_migrations_are_named_by_timestamp() -> None:
    offenders = []
    for path in MIGRATIONS.glob("*.sql"):
        prefix = path.name.split("_", 1)[0]
        if len(prefix) == 3 and prefix <= LAST_SEQUENTIAL_MIGRATION:
            continue
        match = TIMESTAMPED_MIGRATION.fullmatch(path.name)
        if match is None:
            offenders.append(path.name)
            continue
        try:
            datetime.strptime(match.group(1), "%Y%m%d%H%M")
        except ValueError:
            offenders.append(path.name)

    assert not offenders, (
        f"Migrations {sorted(offenders)} must be named YYYYMMDDHHMM_description.sql "
        "(UTC, lowercase snake_case description)."
    )


def test_timestamped_migrations_sort_after_every_sequential_one() -> None:
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    timestamped = [name for name in names if TIMESTAMPED_MIGRATION.fullmatch(name)]

    assert names[len(names) - len(timestamped) :] == timestamped
    assert TIMESTAMPED_MIGRATION.fullmatch("202609241530_example_change.sql")
    assert sorted(["026_last.sql", "202609241530_next.sql"])[-1] == "202609241530_next.sql"
