"""Identity-aware façades for Requirement and resumable-draft operations."""

from __future__ import annotations

from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.identity.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementAccessPort,
)
from smb_requirement_agent.requirements.application.ports.catalogue_pages import (
    CataloguePagesPort,
    DraftPage,
    DraftPageQuery,
    DraftSort,
)
from smb_requirement_agent.requirements.application.ports.screening_requests import (
    ScreeningRequestPort,
)
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirement,
    CreateRequirementInput,
)
from smb_requirement_agent.requirements.application.use_cases.requirement_drafts import (
    CreateRequirementDraft,
    GetRequirementDraft,
    PromoteRequirementDraft,
    RequirementDraftInput,
    SaveRequirementDraft,
)
from smb_requirement_agent.requirements.domain.requirement.entities import (
    Requirement,
    RequirementDraft,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class CreateOwnedRequirement:
    def __init__(
        self,
        create: CreateRequirement,
        access: RequirementAccessPort,
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
        access: RequirementAccessPort,
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
    def __init__(self, get: GetRequirementDraft, access: RequirementAccessPort) -> None:
        self._get = get
        self._access = access

    def execute(self, draft_id: RequirementId, actor: ActorProfile) -> RequirementDraft:
        draft = self._get.execute(draft_id)
        self._access.require_draft_owner(draft_id, actor)
        return draft


class ListOwnedRequirementDrafts:
    """One page of the actor's drafts, or of the drafts nobody owns."""

    def __init__(self, pages: CataloguePagesPort) -> None:
        self._pages = pages

    def execute(
        self,
        actor: ActorProfile,
        *,
        unowned: bool = False,
        q: str | None = None,
        sort: DraftSort = DraftSort.UPDATED_DESC,
        offset: int = 0,
        limit: int = 20,
    ) -> DraftPage:
        return self._pages.drafts(
            DraftPageQuery(None if unowned else actor.id, q, sort, offset, limit)
        )


class SaveOwnedRequirementDraft:
    def __init__(
        self,
        save: SaveRequirementDraft,
        access: RequirementAccessPort,
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
        access_service: RequirementAccessPort,
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
