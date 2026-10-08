"""Authenticate actors and manage Requirement access without provider coupling."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TypeVar

from smb_kernel.identity.ports import (
    IdentityCredential,
    IdentityProviderPort,
)
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.application.errors import (
    ActorNotFoundError,
    RequirementDraftNotFoundError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.external_work import guard_external_work
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.identity.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.identity.application.ports.actor_directory import ActorDirectoryPort
from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementPermission,
)
from smb_requirement_agent.identity.domain.entities import (
    DraftOwnership,
    RequirementAccess,
)
from smb_requirement_agent.identity.domain.errors import (
    AuthorizationDeniedError,
    RequirementAccessConflictError,
)
from smb_requirement_agent.jobs.application.use_cases.job_execution_context import current_attempt
from smb_requirement_agent.jobs.domain.entities import AiJobOperation, AiJobOrigin
from smb_requirement_agent.requirements.application.ports.requirement_draft_repository import (
    RequirementDraftRepositoryPort,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

T = TypeVar("T")


@dataclass(frozen=True)
class RequirementAccessView:
    access: RequirementAccess
    can_claim_owner: bool
    can_manage_assignments: bool
    can_confirm_analysis: bool
    can_export_approved_revisions: bool
    can_manage_content: bool
    can_govern: bool


class ResolveCurrentActor:
    def __init__(
        self,
        identity: IdentityProviderPort,
        actors: ActorDirectoryPort,
    ) -> None:
        self._identity = identity
        self._actors = actors

    def execute(self, credential: IdentityCredential) -> ActorProfile:
        actor = self._identity.authenticate(credential)
        self._actors.record(actor)
        return actor


class SearchKnownActors:
    def __init__(self, actors: ActorDirectoryPort) -> None:
        self._actors = actors

    def execute(self, query: str | None, limit: int) -> tuple[ActorProfile, ...]:
        return tuple(self._actors.search(query, limit))


class RequirementAccessService:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        drafts: RequirementDraftRepositoryPort,
        access: AccessRepositoryPort,
        actors: ActorDirectoryPort,
        clock: ClockPort,
        transactions: TransactionManagerPort,
        analysis_audits: AnalysisAuditRepositoryPort,
    ) -> None:
        self._requirements = requirements
        self._drafts = drafts
        self._access = access
        self._actors = actors
        self._clock = clock
        self._transactions = transactions
        self._analysis_audits = analysis_audits

    def requirement_view(
        self, requirement_id: RequirementId, current: ActorProfile
    ) -> RequirementAccessView:
        self._require_requirement(requirement_id)
        access = self._requirement_access(requirement_id)
        is_owner = access.is_owner(current.id)
        return RequirementAccessView(
            access,
            access.owner is None,
            is_owner,
            is_owner,
            access.includes(current.id),
            access.includes(current.id),
            is_owner,
        )

    def require_requirement_member(
        self, requirement_id: RequirementId, current: ActorProfile
    ) -> RequirementAccess:
        """Authorize a Requirement mutation shared by the owner and reviewers."""
        return self.require_requirement_member_id(requirement_id, current.id)

    def require_requirement_member_id(
        self, requirement_id: RequirementId, actor_id: ActorId
    ) -> RequirementAccess:
        """Authorize an actor snapshot used by durable background work."""
        self._require_requirement(requirement_id)
        access = self._requirement_access(requirement_id)
        access.require_member(actor_id)
        return access

    def require_job_controller(
        self,
        requirement_id: RequirementId,
        actor_id: ActorId,
        initiator_id: ActorId,
        *,
        automatic: bool,
    ) -> RequirementAccess:
        """Authorize cancellation or retry by the initiator or current owner."""
        del automatic
        self._require_requirement(requirement_id)
        access = self._requirement_access(requirement_id)
        if actor_id == initiator_id or access.is_owner(actor_id):
            return access
        raise AuthorizationDeniedError(
            "Only the AI job creator or Requirement owner may control this job."
        )

    def require_automatic_job_execution(self, requirement_id: RequirementId) -> RequirementAccess:
        """Allow system work only while the Requirement remains claimed."""
        self._require_requirement(requirement_id)
        access = self._requirement_access(requirement_id)
        if access.owner is None:
            raise AuthorizationDeniedError("Automatic work requires a currently owned Requirement.")
        return access

    def require_answerer(
        self,
        requirement_id: RequirementId,
        current: ActorProfile,
        assignee: ActorId | None,
        *,
        allow_team: bool,
    ) -> None:
        """Authorize answering a clarification question.

        The owner and the question's assignee may always answer. Other team
        members may only when the action allows it (for example, drafting).
        """
        self._require_requirement(requirement_id)
        access = self._requirement_access(requirement_id)
        permitted = access.is_owner(current.id) or assignee == current.id
        if allow_team:
            permitted = permitted or access.includes(current.id)
        if not permitted:
            raise AuthorizationDeniedError(
                "Only the question assignee or Requirement owner may answer it."
            )

    def require_owner_of_either(
        self, first: RequirementId, second: RequirementId, current: ActorProfile
    ) -> None:
        """Authorize an action shared by the owners of two linked Requirements."""
        if not (
            self._requirement_access(first).is_owner(current.id)
            or self._requirement_access(second).is_owner(current.id)
        ):
            raise AuthorizationDeniedError(
                "Only a current owner of either linked Requirement may resolve this conflict."
            )

    def require_requirement_owner(
        self, requirement_id: RequirementId, current: ActorProfile
    ) -> RequirementAccess:
        """Authorize a Requirement-governance or source mutation."""
        self._require_requirement(requirement_id)
        access = self._requirement_access(requirement_id)
        access.require_owner(current.id)
        return access

    def require(
        self,
        requirement_id: RequirementId,
        current: ActorProfile,
        permission: RequirementPermission,
    ) -> RequirementAccess:
        """Check current access, for a caller already inside the Requirement's unit of work."""
        if permission is RequirementPermission.OWNER:
            return self.require_requirement_owner(requirement_id, current)
        return self.require_requirement_member(requirement_id, current)

    @contextmanager
    def mutation(
        self,
        requirement_id: RequirementId,
        current: ActorProfile,
        permission: RequirementPermission,
    ) -> Iterator[None]:
        """Run a mutation authorized on both sides of any provider I/O it performs.

        The single authorization fence for Requirement-scoped mutations. It checks
        access when the unit of work opens, again before provider I/O releases the
        lock and after it returns, and once more before the writes commit, so a
        membership or ownership change during a slow model call is honoured.
        """

        def check() -> None:
            self._transactions.lock_requirement(requirement_id)
            self.require(requirement_id, current, permission)

        with self._transactions.transaction(), guard_external_work(check):
            check()
            yield
            check()

    @contextmanager
    def automatic_mutation(
        self, requirement_id: RequirementId, operation: AiJobOperation
    ) -> Iterator[None]:
        """The same fence for system work: only its bound worker attempt, only while owned."""

        def check() -> None:
            attempt = current_attempt()
            if (
                attempt is None
                or attempt.job.origin is not AiJobOrigin.AUTOMATIC
                or attempt.job.requirement_id != requirement_id
                or attempt.job.operation is not operation
            ):
                raise AuthorizationDeniedError("Automatic work requires its bound worker attempt.")
            self._transactions.lock_requirement(requirement_id)
            current = self._access.get_requirement(requirement_id)
            if current is None or current.owner is None:
                raise AuthorizationDeniedError(
                    "Automatic work requires a currently owned Requirement."
                )

        with self._transactions.transaction(), guard_external_work(check):
            check()
            yield
            check()

    def execute_mutation(
        self,
        requirement_id: RequirementId,
        current: ActorProfile,
        permission: RequirementPermission,
        operation: Callable[[], T],
    ) -> T:
        """`mutation` for callers holding the work as a callable."""
        with self.mutation(requirement_id, current, permission):
            return operation()

    def create_requirement_owner(
        self, requirement_id: RequirementId, actor: ActorProfile
    ) -> RequirementAccess:
        access = RequirementAccess(requirement_id).claim(actor, self._clock.now())
        self._access.save_requirement(access)
        return access

    def claim_requirement(
        self, requirement_id: RequirementId, current: ActorProfile, expected_version: int
    ) -> RequirementAccessView:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._require_requirement(requirement_id)
            existing = self._requirement_access(requirement_id)
            _require_access_version(existing, expected_version)
            access = existing.claim(current, self._clock.now())
            if access is not existing:
                self._access.save_requirement(access)
        return self.requirement_view(requirement_id, current)

    def transfer_requirement(
        self,
        requirement_id: RequirementId,
        current: ActorProfile,
        actor_id: ActorId,
        expected_version: int,
    ) -> RequirementAccessView:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._require_requirement(requirement_id)
            target = self._known_actor(actor_id)
            existing = self._requirement_access(requirement_id)
            _require_access_version(existing, expected_version)
            access = existing.transfer(current, target, self._clock.now())
            if access is not existing:
                self._access.save_requirement(access)
                self._clear_question_assignments(requirement_id, current.id, current)
        return self.requirement_view(requirement_id, current)

    def assign_reviewer(
        self,
        requirement_id: RequirementId,
        current: ActorProfile,
        actor_id: ActorId,
        expected_version: int,
    ) -> RequirementAccessView:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._require_requirement(requirement_id)
            reviewer = self._known_actor(actor_id)
            existing = self._requirement_access(requirement_id)
            _require_access_version(existing, expected_version)
            access = existing.assign_reviewer(current, reviewer, self._clock.now())
            if access is not existing:
                self._access.save_requirement(access)
        return self.requirement_view(requirement_id, current)

    def remove_reviewer(
        self,
        requirement_id: RequirementId,
        current: ActorProfile,
        actor_id: ActorId,
        expected_version: int,
    ) -> RequirementAccessView:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._require_requirement(requirement_id)
            existing = self._requirement_access(requirement_id)
            _require_access_version(existing, expected_version)
            access = existing.remove_reviewer(current, actor_id, self._clock.now())
            if access is not existing:
                self._access.save_requirement(access)
                self._clear_question_assignments(requirement_id, actor_id, current)
        return self.requirement_view(requirement_id, current)

    def create_draft_owner(self, draft_id: RequirementId, actor: ActorProfile) -> DraftOwnership:
        ownership = DraftOwnership(draft_id).claim(actor, self._clock.now())
        self._access.save_draft_ownership(ownership)
        return ownership

    def claim_draft(self, draft_id: RequirementId, current: ActorProfile) -> DraftOwnership:
        with self._transactions.transaction():
            self._transactions.lock_requirement(draft_id)
            if self._drafts.get(draft_id) is None:
                raise RequirementDraftNotFoundError(
                    f"Requirement draft {draft_id.value!r} not found."
                )
            ownership = (
                self._access.get_draft_ownership(draft_id) or DraftOwnership(draft_id)
            ).claim(current, self._clock.now())
            self._access.save_draft_ownership(ownership)
        return ownership

    def require_draft_owner(self, draft_id: RequirementId, current: ActorProfile) -> DraftOwnership:
        if self._drafts.get(draft_id) is None:
            raise RequirementDraftNotFoundError(f"Requirement draft {draft_id.value!r} not found.")
        ownership = self._access.get_draft_ownership(draft_id) or DraftOwnership(draft_id)
        ownership.require_owner(current.id)
        return ownership

    def can_access_draft(self, draft_id: RequirementId, current: ActorProfile) -> bool:
        ownership = self._access.get_draft_ownership(draft_id)
        return (
            ownership is not None
            and ownership.owner is not None
            and ownership.owner.actor.id == current.id
        )

    def _requirement_access(self, requirement_id: RequirementId) -> RequirementAccess:
        return self._access.get_requirement(requirement_id) or RequirementAccess(requirement_id)

    def _require_requirement(self, requirement_id: RequirementId) -> None:
        if self._requirements.get(requirement_id) is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")

    def _known_actor(self, actor_id: ActorId) -> ActorProfile:
        actor = self._actors.get(actor_id)
        if actor is None:
            raise ActorNotFoundError(f"Actor {actor_id.value!r} is not known to this workspace.")
        return actor

    def _clear_question_assignments(
        self, requirement_id: RequirementId, actor_id: ActorId, changed_by: ActorProfile
    ) -> None:
        for question in self._analysis_audits.list_questions(requirement_id):
            if question.is_active and question.assignee and question.assignee.id == actor_id:
                self._analysis_audits.save_question(
                    question.assign(None, changed_by, self._clock.now(), question.version)
                )


def _require_access_version(access: RequirementAccess, expected_version: int) -> None:
    if access.version != expected_version:
        raise RequirementAccessConflictError(
            f"Requirement access changed from version {expected_version} to {access.version}."
        )
