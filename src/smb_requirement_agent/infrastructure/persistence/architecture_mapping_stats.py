"""Counting architecture mappings per catalogue release."""

from __future__ import annotations

from collections import defaultdict

import psycopg
from smb_kernel.persistence.connector import PostgresConnector

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.application.ports.architecture_mapping_stats import MappingCount
from smb_requirement_agent.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.application.ports.feature_repository import FeatureRepositoryPort
from smb_requirement_agent.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.application.ports.story_repository import StoryRepositoryPort

_COUNTS = """
WITH mapped AS (
    SELECT e.requirement_id, f.payload->'architecture'->>'knowledge_version' AS release_id,
           'feature' AS kind
    FROM features f JOIN epics e ON e.epic_id = f.epic_id
    WHERE jsonb_typeof(f.payload->'architecture') = 'object'
    UNION ALL
    SELECT e.requirement_id, s.payload->'architecture'->>'knowledge_version', 'story'
    FROM stories s
    JOIN features f ON f.feature_id = s.feature_id
    JOIN epics e ON e.epic_id = f.epic_id
    WHERE jsonb_typeof(s.payload->'architecture') = 'object'
)
SELECT release_id,
       count(DISTINCT requirement_id),
       count(*) FILTER (WHERE kind = 'feature'),
       count(*) FILTER (WHERE kind = 'story')
FROM mapped GROUP BY release_id ORDER BY release_id
"""


def _count(value: object) -> int:
    return int(str(value))


class PostgresArchitectureMappingStats:
    def __init__(self, connector: PostgresConnector) -> None:
        self._connector = connector

    def by_release(self) -> tuple[MappingCount, ...]:
        try:
            with self._connector.connection() as connection:
                rows = connection.execute(_COUNTS).fetchall()
        except psycopg.Error as exc:
            raise PersistenceError("Architecture mapping counts failed.") from exc
        return tuple(
            MappingCount(str(release), _count(requirements), _count(features), _count(stories))
            for release, requirements, features, stories in rows
        )


class RepositoryArchitectureMappingStats:
    """The same counts by walking the backlog repositories; for in-memory persistence."""

    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        epics: EpicRepositoryPort,
        features: FeatureRepositoryPort,
        stories: StoryRepositoryPort,
    ) -> None:
        self._requirements = requirements
        self._epics = epics
        self._features = features
        self._stories = stories

    def by_release(self) -> tuple[MappingCount, ...]:
        requirements: dict[str, set[str]] = defaultdict(set)
        features: dict[str, int] = defaultdict(int)
        stories: dict[str, int] = defaultdict(int)
        for requirement in self._requirements.list_all():
            epic = self._epics.get_by_requirement_id(requirement.id)
            if epic is None:
                continue
            for feature in self._features.get_by_epic_id(epic.id):
                if feature.architecture is not None:
                    release = feature.architecture.knowledge_version
                    requirements[release].add(requirement.id.value)
                    features[release] += 1
                for story in self._stories.get_by_feature_id(feature.id):
                    if story.architecture is not None:
                        release = story.architecture.knowledge_version
                        requirements[release].add(requirement.id.value)
                        stories[release] += 1
        return tuple(
            MappingCount(release, len(requirements[release]), features[release], stories[release])
            for release in sorted(requirements)
        )
