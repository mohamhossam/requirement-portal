"""UpdateRequirement use case."""

from __future__ import annotations

from dataclasses import dataclass

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    RequirementNotFoundError,
    RequirementVersionConflictError,
)
from smb_requirement_agent.application.ports.domain_events import DomainEventPublisher
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementAccessService,
    RequirementPermission,
)
from smb_requirement_agent.requirements.application.ports.document_repository import (
    DocumentRepositoryPort,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.application.use_cases.requirement_sources import (
    require_usable_source,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.events import RequirementRevised
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementContext,
    RequirementDescription,
    RequirementTitle,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True, kw_only=True)
class UpdateRequirementInput:
    """Input data for updating an existing Requirement."""

    title: str
    description: str
    desired_outcome: str | None = None
    customer_context: str | None = None
    channels: tuple[str, ...] | None = None
    systems: tuple[str, ...] | None = None
    business_rules: tuple[str, ...] | None = None
    constraints: tuple[str, ...] | None = None
    expected_version: int


class UpdateRequirement:
    """Updates the editable fields of an existing Requirement.

    Raises RequirementNotFoundError when the Requirement does not exist.
    Domain invariants (non-empty title/description) are enforced by the
    value objects passed to Requirement.update().

    Invalidation of derived artifacts is a required collaborator: making it
    optional created a second, untested configuration in which a stale analysis
    or Epic could outlive the text it describes.
    """

    def __init__(
        self,
        repository: RequirementRepositoryPort,
        events: DomainEventPublisher,
        clock: ClockPort,
        transactions: TransactionManagerPort,
        *,
        authorization: RequirementAccessService,
        documents: DocumentRepositoryPort,
    ) -> None:
        self._repository = repository
        self._events = events
        self._clock = clock
        self._transactions = transactions
        self._authorization = authorization
        self._documents = documents

    def execute(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        data: UpdateRequirementInput,
    ) -> Requirement:
        with self._authorization.mutation(requirement_id, actor, RequirementPermission.OWNER):
            return self._execute(requirement_id, data)

    def _execute(self, requirement_id: RequirementId, data: UpdateRequirementInput) -> Requirement:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            existing = self._repository.get(requirement_id)
            if existing is None:
                raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
            existing.require_active()
            if data.expected_version != existing.version.value:
                raise RequirementVersionConflictError(
                    f"Requirement {requirement_id.value!r} is at version "
                    f"{existing.version.value}; received {data.expected_version}."
                )

            require_usable_source(
                data.description, tuple(self._documents.list_for_requirement(requirement_id))
            )
            updated = existing.update(
                title=RequirementTitle(data.title),
                description=RequirementDescription(data.description, attachment_backed=True),
                desired_outcome=(
                    existing.desired_outcome
                    if data.desired_outcome is None
                    else _optional_context(data.desired_outcome)
                ),
                customer_context=(
                    existing.customer_context
                    if data.customer_context is None
                    else _optional_context(data.customer_context)
                ),
                channels=existing.channels if data.channels is None else _contexts(data.channels),
                systems=existing.systems if data.systems is None else _contexts(data.systems),
                business_rules=(
                    existing.business_rules
                    if data.business_rules is None
                    else _contexts(data.business_rules)
                ),
                constraints=(
                    existing.constraints
                    if data.constraints is None
                    else _contexts(data.constraints)
                ),
                updated_at=self._clock.now(),
            )
            if _same_source(existing, updated):
                return existing
            self._repository.save(updated)
            self._events.publish(RequirementRevised(requirement_id=requirement_id))
            return updated


def _optional_context(value: str) -> RequirementContext | None:
    return RequirementContext(value) if value.strip() else None


def _contexts(values: tuple[str, ...]) -> tuple[RequirementContext, ...]:
    return tuple(RequirementContext(value) for value in values if value.strip())


def _same_source(left: Requirement, right: Requirement) -> bool:
    return (
        left.title == right.title
        and left.description == right.description
        and left.desired_outcome == right.desired_outcome
        and left.customer_context == right.customer_context
        and left.channels == right.channels
        and left.systems == right.systems
        and left.business_rules == right.business_rules
        and left.constraints == right.constraints
    )
