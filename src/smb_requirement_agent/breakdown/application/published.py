"""What other contexts may call in breakdown (ADR-0103 §1).

- `FeatureLookup`: resolving a Requirement down to one of its Features, which governance's
  `ApproveFeature` builds on.
- `story_set_fingerprint`: the key a Story-quality snapshot is stored under, which governance
  compares when it reuses a snapshot.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from smb_requirement_agent.breakdown.application.errors import (
    EpicNotFoundError,
    FeatureNotFoundError,
)
from smb_requirement_agent.breakdown.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.breakdown.application.ports.feature_repository import (
    FeatureRepositoryPort,
)
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.breakdown.domain.feature.entities import Feature
from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.breakdown.domain.story.quality import StoryQualityEvidence
from smb_requirement_agent.requirements.application.errors import RequirementNotFoundError
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class FeatureLookup:
    """Shared resolution from a requirement down to one Feature."""

    def __init__(
        self,
        requirement_repository: RequirementRepositoryPort,
        epic_repository: EpicRepositoryPort,
        feature_repository: FeatureRepositoryPort,
    ) -> None:
        self._requirements = requirement_repository
        self._epics = epic_repository
        self._features = feature_repository

    def _epic(self, requirement_id: RequirementId) -> Epic:
        if self._requirements.get(requirement_id) is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        epic = self._epics.get_by_requirement_id(requirement_id)
        if epic is None:
            raise EpicNotFoundError(f"No Epic exists for requirement {requirement_id.value!r}.")
        return epic

    def _feature(self, requirement_id: RequirementId, feature_id: FeatureId) -> Feature:
        epic = self._epic(requirement_id)
        feature = self._features.get(epic.id, feature_id)
        if feature is None:
            # Scoped by Epic, so a Feature belonging to a different Epic reads
            # as absent here rather than being editable through this path.
            raise FeatureNotFoundError(
                f"No Feature {feature_id.value!r} under the Epic for requirement "
                f"{requirement_id.value!r}."
            )
        return feature


def story_set_fingerprint(stories: tuple[UserStory, ...], evidence: StoryQualityEvidence) -> str:
    payload = [
        {
            "id": story.id.value,
            "voice": story.voice,
            "criteria": [
                [criterion.given, criterion.when, criterion.then]
                for criterion in story.acceptance_criteria
            ],
        }
        for story in stories
    ]
    canonical = json.dumps(
        {"stories": payload, "evidence": asdict(evidence)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
