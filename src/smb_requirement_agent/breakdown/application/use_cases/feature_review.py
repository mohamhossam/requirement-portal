"""Reading and editing individual Features.

Both operations share the same lookup - resolve the requirement, its Epic, then
one Feature scoped to that Epic. Approving a Feature uses the same lookup from
governance's `approve_feature` (ADR-0103 PR 11).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.application.ports.domain_events import DomainEventPublisher
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.breakdown.application.errors import (
    EpicNotFoundError,
    FeatureNotFoundError,
    FeaturesNotFoundError,
)
from smb_requirement_agent.breakdown.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.breakdown.application.ports.feature_repository import (
    FeatureRepositoryPort,
)
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.breakdown.domain.feature.entities import Feature
from smb_requirement_agent.breakdown.domain.feature.errors import (
    InvalidFeatureContentError,
)
from smb_requirement_agent.breakdown.domain.feature.events import FeatureChanged
from smb_requirement_agent.breakdown.domain.feature.value_objects import (
    DeliveryDrop,
    FeatureId,
    FeatureName,
    FeatureOutcome,
    SplittingPattern,
    SplittingRationale,
)
from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementAccessPort,
    RequirementPermission,
)
from smb_requirement_agent.requirements.application.errors import RequirementNotFoundError
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.enums import supported_values, value_of
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True)
class EditFeatureInput:
    """Input data for editing a Feature."""

    name: str
    outcome: str
    delivery_drop: str
    splitting_pattern: str
    splitting_rationale: str
    source_reconciled: bool = False
    expected_version: int = 1


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


class GetFeatures(FeatureLookup):
    """Returns the Feature set for a requirement's Epic, in generation order."""

    def execute(self, requirement_id: RequirementId) -> list[Feature]:
        epic = self._epic(requirement_id)
        features = self._features.get_by_epic_id(epic.id)
        if not features:
            raise FeaturesNotFoundError(
                f"No Features have been generated for requirement {requirement_id.value!r}."
            )
        return features


class EditFeature(FeatureLookup):
    """Applies a human edit to one Feature, leaving its siblings untouched."""

    def __init__(
        self,
        requirement_repository: RequirementRepositoryPort,
        epic_repository: EpicRepositoryPort,
        feature_repository: FeatureRepositoryPort,
        events: DomainEventPublisher,
        transactions: TransactionManagerPort,
        *,
        authorization: RequirementAccessPort,
    ) -> None:
        super().__init__(requirement_repository, epic_repository, feature_repository)
        self._events = events
        self._transactions = transactions
        self._authorization = authorization

    def execute(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        data: EditFeatureInput,
    ) -> Feature:
        with self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER):
            return self._execute(requirement_id=requirement_id, feature_id=feature_id, data=data)

    def _execute(
        self,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        data: EditFeatureInput,
    ) -> Feature:
        feature = self._feature(requirement_id, feature_id)
        if feature.version != data.expected_version:
            raise ArtifactVersionConflictError(
                f"Feature changed from version {data.expected_version} to "
                f"{feature.version}. Reload it."
            )
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            if self._feature(requirement_id, feature_id) != feature:
                raise ArtifactVersionConflictError(
                    "Feature changed before this edit could be committed. Reload it."
                )
            edited = feature.edit(
                name=FeatureName(data.name),
                outcome=FeatureOutcome(data.outcome),
                delivery_drop=_parse_drop(data.delivery_drop),
                splitting_pattern=_parse_pattern(data.splitting_pattern),
                splitting_rationale=SplittingRationale(data.splitting_rationale),
                source_reconciled=data.source_reconciled,
            )
            self._features.save(edited)
            self._events.publish(
                FeatureChanged(requirement_id=requirement_id, feature_id=edited.id)
            )
        return edited


def _parse_drop(raw: str) -> DeliveryDrop:
    return _parse_choice(DeliveryDrop, raw, "delivery drop")


def _parse_pattern(raw: str) -> SplittingPattern:
    return _parse_choice(SplittingPattern, raw, "splitting pattern")


def _parse_choice[T: Enum](enum_type: type[T], raw: str, field: str) -> T:
    """Map caller input onto a domain enum.

    Unlike the generator's equivalent, an unrecognised value here is the
    caller's mistake, so it raises the Feature content error that maps to 422.
    """
    member = value_of(enum_type, raw)
    if member is None:
        raise InvalidFeatureContentError(
            f"Unsupported {field} {raw!r}. Supported: {supported_values(enum_type)}."
        )
    return member
