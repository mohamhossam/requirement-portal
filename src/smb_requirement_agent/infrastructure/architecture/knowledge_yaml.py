"""The immutable packaged seed catalogue, read from the shipped YAML file."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import yaml

from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    InvalidKnowledgeError,
    KnowledgeReleaseStatus,
)
from smb_requirement_agent.infrastructure.architecture.catalogue_files import content_from_mapping
from smb_requirement_agent.infrastructure.architecture.yaml_knowledge import default_knowledge_path


def knowledge_from_yaml(text: str) -> ArchitectureKnowledge:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise InvalidKnowledgeError("Architecture YAML has invalid content.") from exc
    if not isinstance(raw, dict) or not raw.get("version"):
        raise InvalidKnowledgeError("Architecture YAML needs a version.")
    content = content_from_mapping(raw)
    return ArchitectureKnowledge(
        str(raw["version"]),
        1,
        content.systems,
        content.relationships,
        capability_domains=content.capability_domains,
        landscape_domains=content.landscape_domains,
        products=content.products,
        journeys=content.journeys,
    )


def seed_knowledge() -> ArchitectureKnowledge:
    path: Path = default_knowledge_path()
    draft = knowledge_from_yaml(path.read_text(encoding="utf-8"))
    return replace(
        draft,
        status=KnowledgeReleaseStatus.PUBLISHED,
        built_revision=1,
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        published_by="packaged-seed",
        name="Initial catalogue",
    )
