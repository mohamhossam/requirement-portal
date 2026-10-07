"""Identity-aware façades for Requirement and resumable-draft operations."""

from __future__ import annotations

from smb_requirement_agent.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.application.ports.screening_requests import ScreeningRequestPort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.create_requirement import (
    CreateRequirement,
    CreateRequirementInput,
)
from smb_requirement_agent.application.use_cases.identity_access import RequirementAccessService
from smb_requirement_agent.application.use_cases.requirement_drafts import (
    CreateRequirementDraft,
    GetRequirementDraft,
    ListRequirementDrafts,
    PromoteRequirementDraft,
    RequirementDraftInput,
    SaveRequirementDraft,
)
from smb_requirement_agent.domain.requirement.entities import Requirement, RequirementDraft
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class CreateOwnedRequirement:
    def __init__(
        self,
        create: CreateRequirement,
        access: RequirementAccessService,
        transactions: TransactionManagerPort,
        knowledge: ScreeningRequestPort,
    ) -> None:
        self._create = create
        self._access = access
        self._transactions = transactions
        self._knowledge = knowledge

    def execute(self, data: CreateRequirementInput, actor: ActorProfile) -> Requirement:
        with self._transactions.transaction():
            requirement = self._create.execute(data)
            self._transactions.lock_requirement(requirement.id)
            self._access.create_requirement_owner(requirement.id, actor)
            self._knowledge.schedule(requirement.id)
        return requirement


class CreateOwnedRequirementDraft:
    def __init__(
        self,
        create: CreateRequirementDraft,
        access: RequirementAccessService,
        transactions: TransactionManagerPort,
    ) -> None:
        self._create = create
        self._access = access
        self._transactions = transactions

    def execute(self, data: RequirementDraftInput, actor: ActorProfile) -> RequirementDraft:
        with self._transactions.transaction():
            draft = self._create.execute(data)
            self._transactions.lock_requirement(draft.id)
            self._access.create_draft_owner(draft.id, actor)
        return draft


class GetOwnedRequirementDraft:
    def __init__(self, get: GetRequirementDraft, access: RequirementAccessService) -> None:
        self._get = get
        self._access = access

    def execute(self, draft_id: RequirementId, actor: ActorProfile) -> RequirementDraft:
        draft = self._get.execute(draft_id)
        self._access.require_draft_owner(draft_id, actor)
        return draft


class ListOwnedRequirementDrafts:
    def __init__(
        self,
        listed: ListRequirementDrafts,
        repository: AccessRepositoryPort,
    ) -> None:
        self._listed = listed
        self._repository = repository

    def execute(
        self, actor: ActorProfile, *, unowned: bool = False
    ) -> tuple[RequirementDraft, ...]:
        result: list[RequirementDraft] = []
        for draft in self._listed.execute():
            ownership = self._repository.get_draft_ownership(draft.id)
            if unowned and (ownership is None or ownership.owner is None):
                result.append(draft)
            elif (
                not unowned
                and ownership is not None
                and ownership.owner is not None
                and ownership.owner.actor.id == actor.id
            ):
                result.append(draft)
        return tuple(result)


class SaveOwnedRequirementDraft:
    def __init__(
        self,
        save: SaveRequirementDraft,
        access: RequirementAccessService,
        transactions: TransactionManagerPort,
    ) -> None:
        self._save = save
        self._access = access
        self._transactions = transactions

    def execute(
        self,
        draft_id: RequirementId,
        data: RequirementDraftInput,
        expected_version: int,
        actor: ActorProfile,
    ) -> RequirementDraft:
        with self._transactions.transaction():
            self._transactions.lock_requirement(draft_id)
            self._access.require_draft_owner(draft_id, actor)
            return self._save.execute(draft_id, data, expected_version)


class PromoteOwnedRequirementDraft:
    def __init__(
        self,
        promote: PromoteRequirementDraft,
        access_service: RequirementAccessService,
        access_repository: AccessRepositoryPort,
        transactions: TransactionManagerPort,
        knowledge: ScreeningRequestPort,
    ) -> None:
        self._promote = promote
        self._access_service = access_service
        self._access_repository = access_repository
        self._transactions = transactions
        self._knowledge = knowledge

    def execute(
        self, draft_id: RequirementId, expected_version: int, actor: ActorProfile
    ) -> Requirement:
        with self._transactions.transaction():
            self._transactions.lock_requirement(draft_id)
            self._access_service.require_draft_owner(draft_id, actor)
            requirement = self._promote.execute(draft_id, expected_version)
            self._transactions.lock_requirement(requirement.id)
            self._access_service.create_requirement_owner(requirement.id, actor)
            self._access_repository.delete_draft_ownership(draft_id)
            self._knowledge.schedule(requirement.id)
        return requirement
