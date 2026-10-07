"""Persistence boundary for resumable Requirement drafts."""

from abc import ABC, abstractmethod

from smb_requirement_agent.requirements.domain.requirement.entities import RequirementDraft
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class RequirementDraftRepositoryPort(ABC):
    @abstractmethod
    def add(self, draft: RequirementDraft) -> None: ...

    @abstractmethod
    def get(self, draft_id: RequirementId) -> RequirementDraft | None: ...

    @abstractmethod
    def list_all(self) -> list[RequirementDraft]: ...

    @abstractmethod
    def save(self, draft: RequirementDraft) -> None: ...

    @abstractmethod
    def delete(self, draft_id: RequirementId) -> None: ...
