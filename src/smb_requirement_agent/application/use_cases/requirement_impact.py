"""Preview and safely commit source changes that invalidate derived work."""

from dataclasses import dataclass

from smb_requirement_agent.application.errors import (
    RequirementImpactAcknowledgementRequiredError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.requirement_worklist import (
    RequirementWorklistSnapshot,
    RequirementWorklistSnapshotPort,
)
from smb_requirement_agent.application.ports.screening_requests import ScreeningRequestPort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.update_requirement import (
    UpdateRequirement,
    UpdateRequirementInput,
)
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True)
class RequirementImpactPreview:
    requirement_id: RequirementId
    requirement_version: int
    analysis_count: int
    epic_count: int
    feature_count: int
    story_count: int
    source_changed: bool

    @property
    def requires_acknowledgement(self) -> bool:
        return self.source_changed and any(
            (self.analysis_count, self.epic_count, self.feature_count, self.story_count)
        )


class PreviewRequirementImpact:
    def __init__(self, snapshots: RequirementWorklistSnapshotPort) -> None:
        self._snapshots = snapshots

    def execute(
        self, requirement_id: RequirementId, data: UpdateRequirementInput
    ) -> RequirementImpactPreview:
        snapshot = self._find(requirement_id)
        return RequirementImpactPreview(
            requirement_id,
            snapshot.requirement.version.value,
            int(snapshot.analysis is not None),
            int(snapshot.epic is not None),
            len(snapshot.features),
            len(snapshot.stories),
            _source_changed(snapshot.requirement, data),
        )

    def _find(self, requirement_id: RequirementId) -> RequirementWorklistSnapshot:
        for snapshot in self._snapshots.list_snapshots():
            if snapshot.requirement.id == requirement_id:
                return snapshot
        raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")


class UpdateRequirementWithImpact:
    def __init__(
        self,
        update: UpdateRequirement,
        preview: PreviewRequirementImpact,
        transactions: TransactionManagerPort,
        knowledge: ScreeningRequestPort,
    ) -> None:
        self._update = update
        self._preview = preview
        self._transactions = transactions
        self._knowledge = knowledge

    def execute(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        data: UpdateRequirementInput,
        *,
        impact_acknowledged: bool,
    ) -> Requirement:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            impact = self._preview.execute(requirement_id, data)
            if impact.requires_acknowledgement and not impact_acknowledged:
                raise RequirementImpactAcknowledgementRequiredError(
                    "This source change affects generated content; preview and acknowledge "
                    "the impact before saving."
                )
            requirement = self._update.execute(actor, requirement_id, data)
            self._knowledge.schedule(requirement_id)
            return requirement


def _source_changed(requirement: Requirement, data: UpdateRequirementInput) -> bool:
    desired_outcome = (
        requirement.desired_outcome.value if requirement.desired_outcome is not None else ""
    )
    customer_context = (
        requirement.customer_context.value if requirement.customer_context is not None else ""
    )

    def normalized(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(value.strip() for value in values if value.strip())

    return any(
        (
            data.title.strip() != requirement.title.value,
            data.description.strip() != requirement.description.value,
            data.desired_outcome is not None and data.desired_outcome.strip() != desired_outcome,
            data.customer_context is not None and data.customer_context.strip() != customer_context,
            data.channels is not None
            and normalized(data.channels) != tuple(item.value for item in requirement.channels),
            data.systems is not None
            and normalized(data.systems) != tuple(item.value for item in requirement.systems),
            data.business_rules is not None
            and normalized(data.business_rules)
            != tuple(item.value for item in requirement.business_rules),
            data.constraints is not None
            and normalized(data.constraints)
            != tuple(item.value for item in requirement.constraints),
        )
    )
