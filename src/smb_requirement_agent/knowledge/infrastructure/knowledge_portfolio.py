"""The Requirement corpus and its findings, row by row, and the nudges sent about them (B2).

Rows carry identity and state only: an owner is an id and a display name, never an email.
A finding is in force on the Knowledge step's own rule, as `corpus_counts` counts it:
actionable, with both Requirements still at the versions it judged.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from threading import RLock
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from smb_kernel.persistence.connector import PostgresConnector

from smb_requirement_agent.identity.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.infrastructure.persistence.database_errors import database_error
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.knowledge.application.ports.corpus_membership import CorpusMembershipPort
from smb_requirement_agent.knowledge.application.ports.knowledge_portfolio import (
    CorpusEntry,
    CorpusQuery,
    FindingEntry,
    FindingNudge,
    FindingQuery,
    FindingSide,
    NudgeMark,
    PersonName,
    RetiredMark,
    finding_age,
)
from smb_requirement_agent.knowledge.domain.entities import KnowledgeFinding
from smb_requirement_agent.knowledge.infrastructure.requirement_knowledge_repository import (
    InMemoryRequirementKnowledgeStore,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.value_objects import RequirementStatus
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

_IN_FORCE = """
    COALESCE(f.payload->>'status', 'open') IN ('open', 'resolution_pending')
    AND COALESCE((subject.payload->>'version')::integer, 1)
        = (f.payload->>'subject_version')::integer
    AND COALESCE((related.payload->>'version')::integer, 1)
        = (f.payload->>'related_version')::integer
"""

_CORPUS = f"""
WITH in_force AS (
    SELECT f.subject_requirement_id AS one, f.related_requirement_id AS other
    FROM requirement_knowledge_findings f
    JOIN requirements subject ON subject.requirement_id = f.subject_requirement_id
    JOIN requirements related ON related.requirement_id = f.related_requirement_id
    WHERE {_IN_FORCE}
), open_counts AS (
    SELECT requirement_id, count(*) AS open_findings FROM (
        SELECT one AS requirement_id FROM in_force UNION ALL SELECT other FROM in_force
    ) sides GROUP BY requirement_id
), screened AS (
    SELECT requirement_id, max(generated_at) AS at
    FROM requirement_knowledge_screens GROUP BY requirement_id
)
SELECT r.requirement_id, r.payload->>'title', r.payload->>'status',
       a.payload->'owner'->'actor'->>'id', a.payload->'owner'->'actor'->>'display_name',
       s.at, COALESCE(c.open_findings, 0), m.changed_at, m.actor_name, m.reason
FROM requirements r
LEFT JOIN requirement_access a ON a.requirement_id = r.requirement_id
LEFT JOIN screened s ON s.requirement_id = r.requirement_id
LEFT JOIN open_counts c ON c.requirement_id = r.requirement_id
LEFT JOIN requirement_corpus_membership m
       ON m.requirement_id = r.requirement_id AND m.state = 'retired'
WHERE (%(owner)s::text IS NULL OR a.payload->'owner'->'actor'->>'id' = %(owner)s)
  AND (%(text)s = '' OR r.payload->>'title' ILIKE %(pattern)s ESCAPE '\\')
  AND (NOT %(open_only)s OR COALESCE(c.open_findings, 0) > 0)
  AND (%(since)s::timestamptz IS NULL OR s.at IS NULL OR s.at < %(since)s)
  AND (%(only)s::text[] IS NULL OR r.requirement_id = ANY(%(only)s))
  AND NOT (r.requirement_id = ANY(%(excluding)s::text[]))
  AND (NOT %(retired_only)s OR m.requirement_id IS NOT NULL)
ORDER BY lower(r.payload->>'title'), r.requirement_id
OFFSET %(offset)s LIMIT %(limit)s
"""  # noqa: S608 - constant fragments only

_FINDINGS = f"""
SELECT f.finding_id, f.payload->>'kind', f.payload->>'rationale', s.generated_at,
       f.subject_requirement_id, subject.payload->>'title',
       sa.payload->'owner'->'actor'->>'id', sa.payload->'owner'->'actor'->>'display_name',
       f.related_requirement_id, related.payload->>'title',
       ra.payload->'owner'->'actor'->>'id', ra.payload->'owner'->'actor'->>'display_name',
       n.nudged_at, n.actor_name
FROM requirement_knowledge_findings f
JOIN requirement_knowledge_screens s ON s.screen_id = f.screen_id
JOIN requirements subject ON subject.requirement_id = f.subject_requirement_id
JOIN requirements related ON related.requirement_id = f.related_requirement_id
LEFT JOIN requirement_access sa ON sa.requirement_id = f.subject_requirement_id
LEFT JOIN requirement_access ra ON ra.requirement_id = f.related_requirement_id
LEFT JOIN LATERAL (
    SELECT nudged_at, actor_name FROM knowledge_finding_nudges
    WHERE finding_id = f.finding_id ORDER BY nudged_at DESC LIMIT 1
) n ON true
WHERE {_IN_FORCE}
  AND (%(kind)s::text IS NULL OR f.payload->>'kind' = %(kind)s)
  AND (%(age)s::text IS NULL
       OR (%(age)s = 'under_7_days' AND %(now)s - s.generated_at < interval '7 days')
       OR (%(age)s = 'from_7_to_30_days'
           AND %(now)s - s.generated_at >= interval '7 days'
           AND %(now)s - s.generated_at <= interval '30 days')
       OR (%(age)s = 'over_30_days' AND %(now)s - s.generated_at > interval '30 days'))
  AND (%(owner)s::text IS NULL
       OR sa.payload->'owner'->'actor'->>'id' = %(owner)s
       OR ra.payload->'owner'->'actor'->>'id' = %(owner)s)
ORDER BY s.generated_at, f.finding_id
OFFSET %(offset)s LIMIT %(limit)s
"""  # noqa: S608 - constant fragments only


def _like(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _person(person_id: object, name: object) -> PersonName | None:
    return PersonName(str(person_id), str(name)) if person_id and name else None


class PostgresKnowledgePortfolio:
    def __init__(self, connector: PostgresConnector) -> None:
        self._connector = connector

    def corpus(self, query: CorpusQuery, offset: int, limit: int) -> tuple[CorpusEntry, ...]:
        parameters = {
            "owner": query.owner_id,
            "text": query.text,
            "pattern": _like(query.text),
            "open_only": query.open_findings_only,
            "since": query.not_screened_since,
            "only": sorted(query.only) if query.only is not None else None,
            "excluding": sorted(query.excluding),
            "retired_only": query.retired_only,
            "offset": offset,
            "limit": limit,
        }
        rows = self._read(_CORPUS, parameters, "Requirement corpus rows")
        return tuple(
            CorpusEntry(
                str(row[0]),
                str(row[1] or ""),
                row[2] == RequirementStatus.DUPLICATE.value,
                _person(row[3], row[4]),
                row[5] if isinstance(row[5], datetime) else None,
                int(str(row[6] or 0)),
                RetiredMark(row[7], str(row[8]), str(row[9]))
                if isinstance(row[7], datetime)
                else None,
            )
            for row in rows
        )

    def findings(self, query: FindingQuery, offset: int, limit: int) -> tuple[FindingEntry, ...]:
        parameters = {
            "kind": query.kind,
            "age": query.age.value if query.age is not None else None,
            "now": query.now,
            "owner": query.owner_id,
            "offset": offset,
            "limit": limit,
        }
        rows = self._read(_FINDINGS, parameters, "Requirement findings")
        return tuple(
            FindingEntry(
                str(row[0]),
                str(row[1]),
                str(row[2] or ""),
                row[3],
                FindingSide(str(row[4]), str(row[5] or ""), _person(row[6], row[7])),
                FindingSide(str(row[8]), str(row[9] or ""), _person(row[10], row[11])),
                NudgeMark(row[12], str(row[13])) if isinstance(row[12], datetime) else None,
            )
            for row in rows
            if isinstance(row[3], datetime)
        )

    def _read(self, sql: str, parameters: dict[str, Any], what: str) -> list[tuple[Any, ...]]:
        try:
            with self._connector.connection() as connection:
                return list(connection.execute(sql, parameters).fetchall())
        except psycopg.Error as exc:
            raise database_error(exc, f"{what} could not be read.") from exc


class PostgresFindingNudges:
    """Written inside the nudge's transaction, beside its notifications."""

    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def latest(self, finding_id: str) -> FindingNudge | None:
        with self._store.connection() as connection:
            row: tuple[Any, ...] | None = connection.execute(
                "SELECT nudge_id, finding_id, actor_id, actor_name, nudged_at, recipients "
                "FROM knowledge_finding_nudges WHERE finding_id=%s "
                "ORDER BY nudged_at DESC LIMIT 1",
                (finding_id,),
            ).fetchone()
        if row is None:
            return None
        return FindingNudge(
            str(row[0]), str(row[1]), str(row[2]), str(row[3]), row[4], tuple(row[5] or ())
        )

    def add(self, nudge: FindingNudge) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "INSERT INTO knowledge_finding_nudges "
                "(nudge_id, finding_id, actor_id, actor_name, nudged_at, recipients) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    nudge.nudge_id,
                    nudge.finding_id,
                    nudge.actor_id,
                    nudge.actor_name,
                    nudge.nudged_at,
                    Jsonb(list(nudge.recipients)),
                ),
            )


class InMemoryFindingNudges:
    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self._nudges: list[FindingNudge] = []

    def snapshot_state(self) -> Any:
        with self._lock:
            return deepcopy(self._nudges)

    def restore_state(self, state: Any) -> None:
        with self._lock:
            self._nudges = deepcopy(state)

    def latest(self, finding_id: str) -> FindingNudge | None:
        with self._lock:
            found = [item for item in self._nudges if item.finding_id == finding_id]
        return max(found, key=lambda item: item.nudged_at) if found else None

    def add(self, nudge: FindingNudge) -> None:
        with self._lock:
            self._nudges.append(nudge)


class RepositoryKnowledgePortfolio:
    """The same rows from the repositories; for in-memory persistence."""

    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        access: AccessRepositoryPort,
        knowledge: InMemoryRequirementKnowledgeStore,
        nudges: InMemoryFindingNudges,
        membership: CorpusMembershipPort | None = None,
    ) -> None:
        self._requirements = requirements
        self._access = access
        self._knowledge = knowledge
        self._nudges = nudges
        self._membership = membership

    def _owner(self, requirement_id: RequirementId) -> PersonName | None:
        access = self._access.get_requirement(requirement_id)
        if access is None or access.owner is None:
            return None
        return PersonName(access.owner.actor.id.value, access.owner.actor.display_name)

    def _in_force(
        self, everyone: dict[RequirementId, Requirement]
    ) -> list[tuple[KnowledgeFinding, datetime]]:
        def current(finding: KnowledgeFinding) -> bool:
            subject = everyone.get(finding.subject_requirement_id)
            related = everyone.get(finding.related_requirement_id)
            return (
                finding.actionable
                and subject is not None
                and related is not None
                and subject.version.value == finding.subject_version
                and related.version.value == finding.related_version
            )

        return [(item, at) for item, at in self._knowledge.raised_findings() if current(item)]

    def corpus(self, query: CorpusQuery, offset: int, limit: int) -> tuple[CorpusEntry, ...]:
        everyone = {item.id: item for item in self._requirements.list_all()}
        open_counts: dict[RequirementId, int] = {}
        for finding, _ in self._in_force(everyone):
            for side in (finding.subject_requirement_id, finding.related_requirement_id):
                open_counts[side] = open_counts.get(side, 0) + 1
        retired = self._membership.retired() if self._membership else {}
        entries = []
        for requirement in everyone.values():
            screen = self._knowledge.current_screen(requirement.id)
            membership = retired.get(requirement.id.value)
            entry = CorpusEntry(
                requirement.id.value,
                requirement.title.value,
                requirement.status is RequirementStatus.DUPLICATE,
                self._owner(requirement.id),
                screen.provenance.generated_at if screen is not None else None,
                open_counts.get(requirement.id, 0),
                RetiredMark(membership.changed_at, membership.actor.display_name, membership.reason)
                if membership is not None
                else None,
            )
            if self._matches(entry, query):
                entries.append(entry)
        entries.sort(key=lambda item: (item.title.lower(), item.requirement_id))
        return tuple(entries[offset : offset + limit])

    @staticmethod
    def _matches(entry: CorpusEntry, query: CorpusQuery) -> bool:
        return (
            (
                query.owner_id is None
                or (entry.owner is not None and entry.owner.id == query.owner_id)
            )
            and query.text.casefold() in entry.title.casefold()
            and (not query.open_findings_only or entry.open_findings > 0)
            and (
                query.not_screened_since is None
                or entry.last_screened_at is None
                or entry.last_screened_at < query.not_screened_since
            )
            and (query.only is None or entry.requirement_id in query.only)
            and entry.requirement_id not in query.excluding
            and (not query.retired_only or entry.retired is not None)
        )

    def findings(self, query: FindingQuery, offset: int, limit: int) -> tuple[FindingEntry, ...]:
        everyone = {item.id: item for item in self._requirements.list_all()}
        entries = []
        for finding, raised_at in self._in_force(everyone):
            subject, related = (
                everyone[finding.subject_requirement_id],
                everyone[finding.related_requirement_id],
            )
            nudge = self._nudges.latest(finding.id.value)
            entry = FindingEntry(
                finding.id.value,
                finding.kind.value,
                finding.rationale,
                raised_at,
                FindingSide(subject.id.value, subject.title.value, self._owner(subject.id)),
                FindingSide(related.id.value, related.title.value, self._owner(related.id)),
                NudgeMark(nudge.nudged_at, nudge.actor_name) if nudge is not None else None,
            )
            owners = {side.owner.id for side in (entry.subject, entry.related) if side.owner}
            if (
                (query.kind is None or entry.kind == query.kind)
                and (query.age is None or finding_age(query.now - raised_at) is query.age)
                and (query.owner_id is None or query.owner_id in owners)
            ):
                entries.append(entry)
        entries.sort(key=lambda item: (item.raised_at, item.finding_id))
        return tuple(entries[offset : offset + limit])
