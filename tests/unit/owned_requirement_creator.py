"""Owned source setup for tests of authorized mutation commands."""

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.application.ports.requirement_repository import RequirementRepositoryPort
from smb_requirement_agent.application.use_cases.create_requirement import (
    CreateRequirement,
    CreateRequirementInput,
)
from smb_requirement_agent.domain.identity.entities import ActorProfile, RequirementAccess
from smb_requirement_agent.domain.requirement.entities import Requirement


class OwnedRequirementCreator:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        access: AccessRepositoryPort,
        actor: ActorProfile,
        clock: ClockPort,
    ) -> None:
        self._create = CreateRequirement(requirements)
        self._access = access
        self._actor = actor
        self._clock = clock

    def execute(self, data: CreateRequirementInput) -> Requirement:
        requirement = self._create.execute(data)
        self._access.save_requirement(
            RequirementAccess(requirement.id).claim(self._actor, self._clock.now())
        )
        return requirement
