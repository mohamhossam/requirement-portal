"""Feature repository port."""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.domain.epic.value_objects import EpicId
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.value_objects import FeatureId


class FeatureRepositoryPort(Protocol):
    """Outbound port for persisting Features, keyed by their parent Epic."""

    def replace_for_epic(
        self, epic_id: EpicId, features: list[Feature], expected_set_version: int
    ) -> int:
        """Replace the whole Feature set for an Epic.

        One call rather than a delete-then-insert the caller must sequence, so
        a set can never be left half-replaced by a caller that forgets a step.
        """
        ...

    def set_version(self, epic_id: EpicId) -> int:
        """Return the positive version of the Feature collection."""
        ...

    def get_by_epic_id(self, epic_id: EpicId) -> list[Feature]:
        """Return the Epic's Features in generation order, or an empty list."""
        ...

    def get(self, epic_id: EpicId, feature_id: FeatureId) -> Feature | None:
        """Return one Feature under the Epic, or None.

        Scoped by Epic so a Feature id from another Epic cannot be reached.
        """
        ...

    def save(self, feature: Feature) -> None:
        """Persist an update to a single existing Feature."""
        ...

    def delete_by_epic_id(self, epic_id: EpicId) -> None:
        """Delete every Feature under an Epic."""
        ...
