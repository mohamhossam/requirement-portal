"""Mapping counts per catalogue release, read from requirement tables (ADR-0099).

The knowledge service shows these counts; requirement work answers them over
`/internal/architecture-mapping/stats` and never says which Requirements.
"""

from __future__ import annotations

import os

import pytest
from smb_kernel.persistence.connector import DirectPostgresConnector

from smb_requirement_agent.infrastructure.persistence.architecture_mapping_stats import (
    PostgresArchitectureMappingStats,
)
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")


def test_mapping_counts_query_runs_against_the_schema() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    counts = PostgresArchitectureMappingStats(DirectPostgresConnector(DATABASE_URL)).by_release()
    assert all(item.requirements <= item.features + item.stories for item in counts)
