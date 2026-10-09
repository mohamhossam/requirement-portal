"""The breakdown context tokens a person was shown (ADR-0103 Amendment 1, F2; PR 11)."""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.application.ports.expected_context import ExpectedContextPort
from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class BreakdownContextPort(ExpectedContextPort, Protocol):
    def epic(self, requirement_id: RequirementId) -> str:
        """The current token for generating this Requirement's Epic."""
        ...

    def features(self, requirement_id: RequirementId) -> str:
        """The current token for generating the Epic's Features."""
        ...

    def stories(self, requirement_id: RequirementId, feature_id: FeatureId) -> str:
        """The current token for generating or changing one Feature's Stories."""
        ...

    def input_artifact_ids(
        self, requirement_id: RequirementId, feature_id: FeatureId | None = None
    ) -> tuple[str, ...]:
        """The Epic, and the Feature if given, whose references the guard rechecks."""
        ...
