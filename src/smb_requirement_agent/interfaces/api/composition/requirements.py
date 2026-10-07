"""Requirement intake: creating, drafting, promoting and editing a Requirement."""

from __future__ import annotations

from dataclasses import dataclass

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.domain_events import DomainEventPublisher
from smb_requirement_agent.application.use_cases.identity_access import RequirementAccessService
from smb_requirement_agent.application.use_cases.requirement_impact import (
    PreviewRequirementImpact,
    UpdateRequirementWithImpact,
)
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters
from smb_requirement_agent.requirements.application.ports.screening_requests import (
    ScreeningRequestPort,
)
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirement,
)
from smb_requirement_agent.requirements.application.use_cases.get_requirement import GetRequirement
from smb_requirement_agent.requirements.application.use_cases.owned_requirements import (
    CreateOwnedRequirement,
    CreateOwnedRequirementDraft,
    GetOwnedRequirementDraft,
    ListOwnedRequirementDrafts,
    PromoteOwnedRequirementDraft,
    SaveOwnedRequirementDraft,
)
from smb_requirement_agent.requirements.application.use_cases.requirement_drafts import (
    CreateRequirementDraft,
    GetRequirementDraft,
    ListRequirementDrafts,
    PromoteRequirementDraft,
    SaveRequirementDraft,
)
from smb_requirement_agent.requirements.application.use_cases.update_requirement import (
    UpdateRequirement,
)


@dataclass(frozen=True)
class RequirementIntakeWiring:
    create_requirement: CreateOwnedRequirement
    get_requirement: GetRequirement
    create_requirement_draft: CreateOwnedRequirementDraft
    get_requirement_draft: GetOwnedRequirementDraft
    list_requirement_drafts: ListOwnedRequirementDrafts
    save_requirement_draft: SaveOwnedRequirementDraft
    promote_requirement_draft: PromoteOwnedRequirementDraft
    preview_requirement_impact: PreviewRequirementImpact
    update_requirement: UpdateRequirementWithImpact


def build_requirement_intake(
    persistence: PersistenceAdapters,
    clock: ClockPort,
    access: RequirementAccessService,
    events: DomainEventPublisher,
    screen_scheduler: ScreeningRequestPort,
) -> RequirementIntakeWiring:
    """Each owned wrapper adds authorization and a unit of work to its base use case.

    Creating, promoting and editing also schedule knowledge screening, which is
    why those routes are rate-limited (ADR-0074).
    """
    drafts = persistence.requirement_draft_repository
    transactions = persistence.transaction_manager
    create_base = CreateRequirement(persistence.requirement_repository)
    preview = PreviewRequirementImpact(persistence.worklist_snapshots)
    update = UpdateRequirement(
        persistence.requirement_repository,
        events,
        clock,
        transactions,
        authorization=access,
        documents=persistence.document_repository,
    )
    promote_base = PromoteRequirementDraft(
        drafts, persistence.document_repository, create_base, transactions
    )
    return RequirementIntakeWiring(
        create_requirement=CreateOwnedRequirement(
            create_base, access, transactions, screen_scheduler
        ),
        get_requirement=GetRequirement(persistence.requirement_repository),
        create_requirement_draft=CreateOwnedRequirementDraft(
            CreateRequirementDraft(drafts, clock), access, transactions
        ),
        get_requirement_draft=GetOwnedRequirementDraft(GetRequirementDraft(drafts), access),
        list_requirement_drafts=ListOwnedRequirementDrafts(
            ListRequirementDrafts(drafts), persistence.access_repository
        ),
        save_requirement_draft=SaveOwnedRequirementDraft(
            SaveRequirementDraft(drafts, clock), access, transactions
        ),
        promote_requirement_draft=PromoteOwnedRequirementDraft(
            promote_base,
            access,
            persistence.access_repository,
            transactions,
            screen_scheduler,
        ),
        preview_requirement_impact=preview,
        update_requirement=UpdateRequirementWithImpact(
            update, preview, transactions, screen_scheduler
        ),
    )
