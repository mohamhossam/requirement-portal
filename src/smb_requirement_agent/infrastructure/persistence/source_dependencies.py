"""Memory and PostgreSQL adapters for the maintained reverse lineage index."""

from dataclasses import replace
from typing import cast

from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.application.ports.source_dependencies import SourceDependency
from smb_requirement_agent.domain.document.lineage import ImpactDecision
from smb_requirement_agent.domain.identity.entities import ActorId
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession


class InMemorySourceDependencies:
    def __init__(self, access: AccessRepositoryPort) -> None:
        self._access = access
        self._rows: dict[str, SourceDependency] = {}
        self._decisions: dict[str, tuple[ImpactDecision, ...]] = {}

    def snapshot_state(self) -> object:
        return self._rows.copy(), self._decisions.copy()

    def restore_state(self, state: object) -> None:
        self._rows, self._decisions = cast(
            tuple[dict[str, SourceDependency], dict[str, tuple[ImpactDecision, ...]]], state
        )

    def replace_current(self, requirement_id: str, rows: tuple[SourceDependency, ...]) -> None:
        self._rows = {
            key: replace(row, current=False, active=False)
            if row.requirement_id == requirement_id
            else row
            for key, row in self._rows.items()
        }
        self._rows.update({row.id: row for row in rows})

    def get(self, dependency_id: str) -> SourceDependency | None:
        return self._rows.get(dependency_id)

    def page(
        self,
        actor_id: ActorId,
        *,
        document_id: str | None = None,
        requirement_id: str | None = None,
        active_only: bool = False,
        target_kind: str | None = None,
        query: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[SourceDependency, ...]:
        rows = []
        for row in sorted(
            self._rows.values(),
            key=lambda r: (not r.current, r.requirement_id, r.target_kind, r.id),
        ):
            access = self._access.get_requirement(RequirementId(row.requirement_id))
            if access is None or not access.includes(actor_id):
                continue
            if document_id is not None and row.lineage.citation.document_id != document_id:
                continue
            if requirement_id is not None and row.requirement_id != requirement_id:
                continue
            if target_kind is not None and row.target_kind != target_kind:
                continue
            if active_only and not row.active:
                continue
            if (
                query.casefold()
                not in f"{row.requirement_title} {row.statement} {row.target_kind}".casefold()
            ):
                continue
            rows.append(row)
        return tuple(rows[offset : offset + limit])

    def for_requirement(self, requirement_id: str) -> tuple[SourceDependency, ...]:
        return tuple(
            row
            for row in self._rows.values()
            if row.requirement_id == requirement_id and row.active
        )

    def decisions(self, dependency_id: str) -> tuple[ImpactDecision, ...]:
        return self._decisions.get(dependency_id, ())

    def decide(self, decision: ImpactDecision, expected_version: int) -> None:
        history = self.decisions(decision.dependency_id)
        if len(history) != expected_version:
            raise ArtifactVersionConflictError("Impact review changed. Reload before deciding.")
        self._decisions[decision.dependency_id] = (*history, decision)


class PostgresSourceDependencies:
    def __init__(self, session: PostgresSession) -> None:
        self._session = session

    def replace_current(self, requirement_id: str, rows: tuple[SourceDependency, ...]) -> None:
        with self._session.connection() as connection:
            connection.execute(
                "UPDATE source_dependencies SET current=false,active=false "
                "WHERE requirement_id=%s AND current",
                (requirement_id,),
            )
            for row in rows:
                connection.execute(
                    """INSERT INTO source_dependencies
                    (id,requirement_id,document_id,target_kind,current,active,search_text,payload)
                    VALUES (%s,%s,%s,%s,true,%s,%s,%s) ON CONFLICT (id) DO UPDATE
                    SET current=true,active=EXCLUDED.active,
                    search_text=EXCLUDED.search_text,payload=EXCLUDED.payload""",
                    (
                        row.id,
                        row.requirement_id,
                        row.lineage.citation.document_id,
                        row.target_kind,
                        row.active,
                        f"{row.requirement_title} {row.statement} {row.target_kind}",
                        Jsonb(TypeAdapter(SourceDependency).dump_python(row, mode="json")),
                    ),
                )

    def get(self, dependency_id: str) -> SourceDependency | None:
        with self._session.connection() as connection:
            row = connection.execute(
                "SELECT payload,current,active FROM source_dependencies WHERE id=%s",
                (dependency_id,),
            ).fetchone()
            return _decode(row) if row else None

    def page(
        self,
        actor_id: ActorId,
        *,
        document_id: str | None = None,
        requirement_id: str | None = None,
        active_only: bool = False,
        target_kind: str | None = None,
        query: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[SourceDependency, ...]:
        # Membership is applied before paging; neither counts nor private titles are returned.
        sql = """SELECT d.payload,d.current,d.active FROM source_dependencies d
            JOIN requirement_worklist_projection w USING (requirement_id)
            WHERE (w.owner_id=%s OR %s=ANY(w.reviewer_ids))"""
        params: list[object] = [actor_id.value, actor_id.value]
        if document_id is not None:
            sql += " AND d.document_id=%s"
            params.append(document_id)
        if requirement_id is not None:
            sql += " AND d.requirement_id=%s"
            params.append(requirement_id)
        if target_kind is not None:
            sql += " AND d.target_kind=%s"
            params.append(target_kind)
        if active_only:
            sql += " AND d.active"
        if query:
            sql += " AND strpos(lower(d.search_text),lower(%s))>0"
            params.append(query)
        sql += " ORDER BY d.current DESC,d.requirement_id,d.target_kind,d.id OFFSET %s LIMIT %s"
        params.extend((offset, limit))
        with self._session.connection() as connection:
            return tuple(_decode(row) for row in connection.execute(sql, tuple(params)).fetchall())

    def for_requirement(self, requirement_id: str) -> tuple[SourceDependency, ...]:
        with self._session.connection() as connection:
            return tuple(
                _decode(row)
                for row in connection.execute(
                    "SELECT payload,current,active FROM source_dependencies "
                    "WHERE requirement_id=%s AND active",
                    (requirement_id,),
                ).fetchall()
            )

    def decisions(self, dependency_id: str) -> tuple[ImpactDecision, ...]:
        with self._session.connection() as connection:
            return tuple(
                TypeAdapter(ImpactDecision).validate_python(row[0])
                for row in connection.execute(
                    "SELECT payload FROM source_impact_decisions "
                    "WHERE dependency_id=%s ORDER BY version",
                    (dependency_id,),
                ).fetchall()
            )

    def decide(self, decision: ImpactDecision, expected_version: int) -> None:
        with self._session.connection() as connection:
            connection.execute(
                "SELECT id FROM source_dependencies WHERE id=%s FOR UPDATE",
                (decision.dependency_id,),
            )
            if len(self.decisions(decision.dependency_id)) != expected_version:
                raise ArtifactVersionConflictError("Impact review changed. Reload before deciding.")
            connection.execute(
                "INSERT INTO source_impact_decisions (dependency_id,version,payload) "
                "VALUES (%s,%s,%s)",
                (
                    decision.dependency_id,
                    decision.version,
                    Jsonb(TypeAdapter(ImpactDecision).dump_python(decision, mode="json")),
                ),
            )


def _decode(row: tuple[object, ...]) -> SourceDependency:
    return replace(
        TypeAdapter(SourceDependency).validate_python(row[0]),
        current=bool(row[1]),
        active=bool(row[2]),
    )
