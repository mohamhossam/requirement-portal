"""CreateRequirement use case."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.intake_limits import (
    require_within_intake_limits,
)
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementContext,
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
    RequirementVersion,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True)
class CreateRequirementInput:
    """Input data for creating a new Requirement."""

    title: str
    description: str
    desired_outcome: str | None = None
    customer_context: str | None = None
    channels: tuple[str, ...] = ()
    systems: tuple[str, ...] = ()
    business_rules: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    current_state: str | None = None
    proposed_state: str | None = None
    out_of_scope: tuple[str, ...] = ()


class CreateRequirement:
    """Creates and persists a new Requirement draft.

    Domain validation (non-empty title/description) is enforced by the
    value objects constructed here; invalid input surfaces as a domain error.
    The ID is generated deterministically by the infrastructure-neutral uuid module;
    no separate ID-generator port is introduced since a single strategy is sufficient.
    """

    def __init__(self, repository: RequirementRepositoryPort) -> None:
        self._repository = repository

    def execute(
        self, data: CreateRequirementInput, *, attachment_backed: bool = False
    ) -> Requirement:
        require_within_intake_limits(
            title=data.title,
            description=data.description,
            desired_outcome=data.desired_outcome,
            customer_context=data.customer_context,
            current_state=data.current_state,
            proposed_state=data.proposed_state,
            lists={
                "channels": data.channels,
                "systems": data.systems,
                "business_rules": data.business_rules,
                "constraints": data.constraints,
                "out_of_scope": data.out_of_scope,
            },
        )
        requirement = Requirement(
            id=RequirementId(str(uuid.uuid4())),
            title=RequirementTitle(data.title),
            description=RequirementDescription(
                data.description, attachment_backed=attachment_backed
            ),
            status=RequirementStatus.DRAFT,
            desired_outcome=_optional_context(data.desired_outcome),
            customer_context=_optional_context(data.customer_context),
            channels=_contexts(data.channels),
            systems=_contexts(data.systems),
            business_rules=_contexts(data.business_rules),
            constraints=_contexts(data.constraints),
            version=RequirementVersion(1),
            current_state=_optional_context(data.current_state),
            proposed_state=_optional_context(data.proposed_state),
            out_of_scope=_contexts(data.out_of_scope),
        )
        self._repository.add(requirement)
        return requirement


def _optional_context(value: str | None) -> RequirementContext | None:
    return RequirementContext(value) if value is not None and value.strip() else None


def _contexts(values: tuple[str, ...]) -> tuple[RequirementContext, ...]:
    return tuple(RequirementContext(value) for value in values if value.strip())
