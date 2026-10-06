"""Counting the Requirement knowledge corpus and the findings in force (A′)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import psycopg
from smb_kernel.persistence.connector import PostgresConnector

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.application.ports.corpus_summary import CorpusCounts
from smb_requirement_agent.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.domain.knowledge.entities import KnowledgeFinding
from smb_requirement_agent.domain.requirement.value_objects import RequirementStatus

_REQUIREMENTS = """
SELECT count(*), count(*) FILTER (WHERE payload->>'status' = 'duplicate') FROM requirements
"""
# A finding is raised with its screen. It stays in force while it is actionable and both
# Requirements are at the versions it judged, which is the Knowledge step's own rule.
_OPEN_FINDINGS = """
SELECT s.generated_at
FROM requirement_knowledge_findings f
JOIN requirement_knowledge_screens s ON s.screen_id = f.screen_id
JOIN requirements subject ON subject.requirement_id = f.subject_requirement_id
JOIN requirements related ON related.requirement_id = f.related_requirement_id
WHERE COALESCE(f.payload->>'status', 'open') IN ('open', 'resolution_pending')
  AND COALESCE((subject.payload->>'version')::integer, 1)
      = (f.payload->>'subject_version')::integer
  AND COALESCE((related.payload->>'version')::integer, 1)
      = (f.payload->>'related_version')::integer
ORDER BY s.generated_at
"""


class PostgresCorpusCounts:
    def __init__(self, connector: PostgresConnector) -> None:
        self._connector = connector

    def counts(self) -> CorpusCounts:
        try:
            with self._connector.connection() as connection:
                requirements = connection.execute(_REQUIREMENTS).fetchone()
                raised = connection.execute(_OPEN_FINDINGS).fetchall()
        except psycopg.Error as exc:
            raise PersistenceError("Requirement corpus counts failed.") from exc
        total, duplicates = requirements if requirements is not None else (0, 0)
        return CorpusCounts(
            int(str(total or 0)),
            int(str(duplicates or 0)),
            tuple(row[0] for row in raised if isinstance(row[0], datetime)),
        )


class RepositoryCorpusCounts:
    """The same counts from the repositories; for in-memory persistence."""

    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        findings: Callable[[], tuple[tuple[KnowledgeFinding, datetime], ...]],
    ) -> None:
        self._requirements = requirements
        self._findings = findings

    def counts(self) -> CorpusCounts:
        everyone = {item.id: item for item in self._requirements.list_all()}
        raised = []
        for finding, at in self._findings():
            subject = everyone.get(finding.subject_requirement_id)
            related = everyone.get(finding.related_requirement_id)
            if (
                finding.actionable
                and subject is not None
                and related is not None
                and subject.version.value == finding.subject_version
                and related.version.value == finding.related_version
            ):
                raised.append(at)
        return CorpusCounts(
            len(everyone),
            sum(1 for item in everyone.values() if item.status is RequirementStatus.DUPLICATE),
            tuple(sorted(raised)),
        )
