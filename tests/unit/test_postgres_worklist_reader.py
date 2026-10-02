"""Bounded SQL behavior of the maintained PostgreSQL worklist reader."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import cast

from smb_requirement_agent.application.ports.requirement_worklist import (
    RequirementWorklistSnapshot,
    RequirementWorklistSnapshotPort,
    WorklistSort,
)
from smb_requirement_agent.application.use_cases.requirement_worklist import (
    RequirementWorklistQuery,
)
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementId,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.infrastructure.persistence.postgres_store import PostgresStore
from smb_requirement_agent.infrastructure.persistence.postgres_worklist import (
    PostgresRequirementWorklistReader,
)

NOW = datetime(2026, 9, 8, 12, tzinfo=UTC)


class QueryResult:
    def __init__(
        self,
        *,
        rows: list[tuple[object, ...]] | None = None,
        row: tuple[object, ...] | None = None,
    ) -> None:
        self.rows = rows or []
        self.row = row

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows

    def fetchone(self) -> tuple[object, ...] | None:
        return self.row


def _projection_row(requirement_id: str, *, status: str = "draft") -> tuple[object, ...]:
    return (
        requirement_id,
        status,
        "capture",
        "analyse",
        0,
        0,
        0,
        0,
        0,
        0,
        NOW,
        None,
    )


class WorklistConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.parameters: list[object] = []

    def execute(self, statement: str, params: object = None) -> QueryResult:
        self.parameters.append(params)
        normalized = " ".join(statement.split())
        self.statements.append(normalized)
        if "SELECT count(*)" in normalized:
            return QueryResult(row=(2,))
        if "GROUP BY workflow_status" in normalized:
            return QueryResult(rows=[("draft", 2)])
        if "SELECT owner_payload" in normalized:
            return QueryResult(rows=[])
        if "workflow_status IN" in normalized:
            return QueryResult(rows=[_projection_row("requirement-a")])
        return QueryResult(
            rows=[_projection_row("requirement-a"), _projection_row("requirement-b")]
        )


class WorklistStore:
    def __init__(self) -> None:
        self.connection_value = WorklistConnection()
        self.hydrated_ids: tuple[str, ...] | None = None

    @contextmanager
    def connection(self) -> Iterator[WorklistConnection]:
        yield self.connection_value

    def list_snapshots(
        self, requirement_ids: tuple[str, ...] | None = None
    ) -> list[RequirementWorklistSnapshot]:
        self.hydrated_ids = requirement_ids
        return [
            RequirementWorklistSnapshot(
                Requirement(
                    RequirementId(raw_id),
                    RequirementTitle(raw_id.replace("requirement-", "").upper()),
                    RequirementDescription(f"Description for {raw_id}"),
                    RequirementStatus.DRAFT,
                ),
                None,
                None,
                (),
                (),
                NOW,
            )
            for raw_id in requirement_ids or ()
        ]


def test_postgres_worklist_filters_pages_and_counts_before_targeted_hydration() -> None:
    store = WorklistStore()
    reader = PostgresRequirementWorklistReader(
        cast(PostgresStore, store), cast(RequirementWorklistSnapshotPort, store)
    )

    result = reader.execute(RequirementWorklistQuery(q="A", sort=WorklistSort.TITLE_ASC, limit=2))

    assert [item.snapshot.requirement.id.value for item in result.requirements] == [
        "requirement-a",
        "requirement-b",
    ]
    assert result.total == 2
    assert result.attention[0].snapshot.requirement.id.value == "requirement-a"
    assert store.hydrated_ids == ("requirement-a", "requirement-b")
    sql = " ".join(store.connection_value.statements)
    assert "requirement_worklist_projection" in sql
    assert 'title_order COLLATE "C" ASC, requirement_id ASC' in sql
    assert "requirement_revisions" not in sql
    assert "breakdown_revisions" not in sql
    assert "requirement_knowledge_chunks" not in sql


def test_search_metacharacters_are_literal_and_casefolded() -> None:
    store = WorklistStore()
    reader = PostgresRequirementWorklistReader(
        cast(PostgresStore, store), cast(RequirementWorklistSnapshotPort, store)
    )
    reader.execute(RequirementWorklistQuery(q="Straße_50%!", limit=2))

    sql = " ".join(store.connection_value.statements)
    assert "LIKE %s ESCAPE '!'" in sql
    assert all(
        "%strasse!_50!%!!%" in cast(tuple[object, ...], params)
        for statement, params in zip(
            store.connection_value.statements, store.connection_value.parameters, strict=True
        )
        if "LIKE %s" in statement
    )
