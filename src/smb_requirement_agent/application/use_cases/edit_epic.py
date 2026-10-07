"""EditEpic use case."""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.application.errors import (
    ArtifactVersionConflictError,
    EpicNotFoundError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.domain_events import DomainEventPublisher
from smb_requirement_agent.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementAccessService,
    RequirementPermission,
)
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.epic.events import EpicChanged
from smb_requirement_agent.domain.epic.value_objects import (
    BusinessCase,
    BusinessOutcome,
    EpicName,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True)
class EditEpicInput:
    """Input data for editing an Epic."""

    name: str
    outcome: str
    business_case: str
    source_reconciled: bool = False
    expected_version: int = 1


class EditEpic:
    """Applies a human edit to an Epic.

    Revoking approval and clearing staleness are the aggregate's decisions,
    not this use case's.
    """

    def __init__(
        self,
        requirement_repository: RequirementRepositoryPort,
        epic_repository: EpicRepositoryPort,
        events: DomainEventPublisher,
        transactions: TransactionManagerPort,
        *,
        authorization: RequirementAccessService,
    ) -> None:
        self._requirements = requirement_repository
        self._epics = epic_repository
        self._events = events
        self._transactions = transactions
        self._authorization = authorization

    def execute(
        self, actor: ActorProfile, requirement_id: RequirementId, data: EditEpicInput
    ) -> Epic:
        with self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER):
            return self._execute(requirement_id=requirement_id, data=data)

    def _execute(self, requirement_id: RequirementId, data: EditEpicInput) -> Epic:
        if self._requirements.get(requirement_id) is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")

        epic = self._epics.get_by_requirement_id(requirement_id)
        if epic is None:
            raise EpicNotFoundError(f"No Epic exists for requirement {requirement_id.value!r}.")
        if epic.version != data.expected_version:
            raise ArtifactVersionConflictError(
                f"Epic changed from version {data.expected_version} to {epic.version}. Reload it."
            )

        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            current = self._epics.get_by_requirement_id(requirement_id)
            if current != epic:
                raise ArtifactVersionConflictError(
                    "Epic changed before this edit could be committed. Reload it."
                )
            edited = epic.edit(
                name=EpicName(data.name),
                outcome=BusinessOutcome(data.outcome),
                business_case=BusinessCase(data.business_case),
                source_reconciled=data.source_reconciled,
            )
            self._epics.save(edited)
            self._events.publish(
                EpicChanged(requirement_id=edited.requirement_id, epic_id=edited.id)
            )
        return edited
