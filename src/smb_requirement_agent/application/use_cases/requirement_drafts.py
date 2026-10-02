"""Create, autosave, resume, list, and promote structured intake drafts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from smb_requirement_agent.application.errors import (
    RequirementDraftNotFoundError,
    RequirementVersionConflictError,
)
from smb_requirement_agent.application.ports.clock import ClockPort
from smb_requirement_agent.application.ports.document_repository import DocumentRepositoryPort
from smb_requirement_agent.application.ports.requirement_draft_repository import (
    RequirementDraftRepositoryPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.create_requirement import (
    CreateRequirement,
    CreateRequirementInput,
)
from smb_requirement_agent.application.use_cases.requirement_sources import (
    has_usable_attachment,
    require_usable_source,
)
from smb_requirement_agent.domain.requirement.entities import Requirement, RequirementDraft
from smb_requirement_agent.domain.requirement.intake_limits import require_within_intake_limits
from smb_requirement_agent.domain.requirement.value_objects import RequirementId, RequirementVersion


@dataclass(frozen=True)
class RequirementDraftInput:
    title: str = ""
    description: str = ""
    desired_outcome: str = ""
    customer_context: str = ""
    channels: tuple[str, ...] = ()
    systems: tuple[str, ...] = ()
    business_rules: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()


class CreateRequirementDraft:
    def __init__(self, drafts: RequirementDraftRepositoryPort, clock: ClockPort) -> None:
        self._drafts = drafts
        self._clock = clock

    def execute(self, data: RequirementDraftInput) -> RequirementDraft:
        require_within_intake_limits(
            title=data.title,
            description=data.description,
            desired_outcome=data.desired_outcome,
            customer_context=data.customer_context,
            lists={
                "channels": data.channels,
                "systems": data.systems,
                "business_rules": data.business_rules,
                "constraints": data.constraints,
            },
        )
        draft = RequirementDraft(
            RequirementId(str(uuid.uuid4())),
            data.title,
            data.description,
            data.desired_outcome,
            data.customer_context,
            data.channels,
            data.systems,
            data.business_rules,
            data.constraints,
            RequirementVersion(1),
            self._clock.now(),
        )
        self._drafts.add(draft)
        return draft


class GetRequirementDraft:
    def __init__(self, drafts: RequirementDraftRepositoryPort) -> None:
        self._drafts = drafts

    def execute(self, draft_id: RequirementId) -> RequirementDraft:
        draft = self._drafts.get(draft_id)
        if draft is None:
            raise RequirementDraftNotFoundError(f"Requirement draft {draft_id.value!r} not found.")
        return draft


class ListRequirementDrafts:
    def __init__(self, drafts: RequirementDraftRepositoryPort) -> None:
        self._drafts = drafts

    def execute(self) -> tuple[RequirementDraft, ...]:
        return tuple(self._drafts.list_all())


class SaveRequirementDraft:
    def __init__(self, drafts: RequirementDraftRepositoryPort, clock: ClockPort) -> None:
        self._drafts = drafts
        self._clock = clock

    def execute(
        self, draft_id: RequirementId, data: RequirementDraftInput, expected_version: int
    ) -> RequirementDraft:
        existing = self._drafts.get(draft_id)
        if existing is None:
            raise RequirementDraftNotFoundError(f"Requirement draft {draft_id.value!r} not found.")
        if existing.version.value != expected_version:
            raise RequirementVersionConflictError(
                f"Requirement draft {draft_id.value!r} is at version "
                f"{existing.version.value}; received {expected_version}."
            )
        revised = existing.revise(
            title=data.title,
            description=data.description,
            desired_outcome=data.desired_outcome,
            customer_context=data.customer_context,
            channels=data.channels,
            systems=data.systems,
            business_rules=data.business_rules,
            constraints=data.constraints,
            updated_at=self._clock.now(),
        )
        self._drafts.save(revised)
        return revised


class PromoteRequirementDraft:
    def __init__(
        self,
        drafts: RequirementDraftRepositoryPort,
        documents: DocumentRepositoryPort,
        create_requirement: CreateRequirement,
        transactions: TransactionManagerPort,
    ) -> None:
        self._drafts = drafts
        self._documents = documents
        self._create_requirement = create_requirement
        self._transactions = transactions

    def execute(self, draft_id: RequirementId, expected_version: int) -> Requirement:
        with self._transactions.transaction():
            self._transactions.lock_requirement(draft_id)
            draft = self._drafts.get(draft_id)
            if draft is None:
                raise RequirementDraftNotFoundError(
                    f"Requirement draft {draft_id.value!r} not found."
                )
            if draft.version.value != expected_version:
                raise RequirementVersionConflictError(
                    f"Requirement draft {draft_id.value!r} is at version "
                    f"{draft.version.value}; received {expected_version}."
                )
            documents = tuple(self._documents.list_for_draft(draft_id))
            require_usable_source(draft.description, documents)
            requirement = self._create_requirement.execute(
                CreateRequirementInput(
                    title=draft.title,
                    description=draft.description,
                    desired_outcome=draft.desired_outcome,
                    customer_context=draft.customer_context or None,
                    channels=draft.channels,
                    systems=draft.systems,
                    business_rules=draft.business_rules,
                    constraints=draft.constraints,
                ),
                attachment_backed=has_usable_attachment(documents),
            )
            for document in documents:
                self._documents.save(document.attach_to_requirement(requirement.id))
            self._drafts.delete(draft_id)
            return requirement
