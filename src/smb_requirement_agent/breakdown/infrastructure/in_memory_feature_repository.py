"""In-memory Feature repository adapter."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.breakdown.domain.epic.value_objects import EpicId
from smb_requirement_agent.breakdown.domain.feature.entities import Feature
from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId


class InMemoryFeatureRepository:
    """Stores Features per Epic, preserving generation order."""

    def __init__(self) -> None:
        self._store: dict[str, list[Feature]] = {}
        self._set_versions: dict[str, int] = {}

    def snapshot_state(self) -> Any:
        return deepcopy(
            (
                self._store,
                self._set_versions,
            )
        )

    def restore_state(self, state: Any) -> None:
        (
            self._store,
            self._set_versions,
        ) = deepcopy(state)

    def replace_for_epic(
        self, epic_id: EpicId, features: list[Feature], expected_set_version: int
    ) -> int:
        current = self.set_version(epic_id)
        if current != expected_set_version:
            raise ArtifactVersionConflictError(
                f"Feature set changed from version {expected_set_version} to {current}. Reload it."
            )
        self._store[epic_id.value] = list(features)
        self._set_versions[epic_id.value] = current + 1
        return current + 1

    def set_version(self, epic_id: EpicId) -> int:
        return self._set_versions.get(epic_id.value, 1)

    def get_by_epic_id(self, epic_id: EpicId) -> list[Feature]:
        return list(self._store.get(epic_id.value, []))

    def get(self, epic_id: EpicId, feature_id: FeatureId) -> Feature | None:
        for feature in self._store.get(epic_id.value, []):
            if feature.id == feature_id:
                return feature
        return None

    def save(self, feature: Feature) -> None:
        features = self._store.get(feature.epic_id.value)
        if features is None:
            raise ArtifactVersionConflictError("The Feature no longer exists. Reload it.")
        current = next((item for item in features if item.id == feature.id), None)
        if current is None:
            raise ArtifactVersionConflictError("The Feature no longer exists. Reload it.")
        if current != feature and feature.version != current.version + 1:
            raise ArtifactVersionConflictError(
                "The Feature changed before this mutation could be saved. Reload it."
            )
        self._store[feature.epic_id.value] = [
            feature if existing.id == feature.id else existing for existing in features
        ]

    def delete_by_epic_id(self, epic_id: EpicId) -> None:
        self._store.pop(epic_id.value, None)
        self._set_versions[epic_id.value] = self.set_version(epic_id) + 1

    def epic_id_for_feature(self, feature_id: FeatureId) -> EpicId | None:
        for epic_id, features in self._store.items():
            if any(feature.id == feature_id for feature in features):
                return EpicId(epic_id)
        return None
