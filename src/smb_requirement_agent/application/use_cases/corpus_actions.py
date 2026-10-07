"""A knowledge admin's actions on the Requirement corpus (Knowledge Center B3).

knowledge-portal calls these over the service-token internal API, naming the admin. Retiring
takes a Requirement out of screening, knowledge search and answer suggestions without touching
it: it stays readable and keeps its version and history. Every open finding that cites it closes
as "source retired". Reinstating returns it; its next screen raises findings afresh. Bulk retry
and reindex only reset failure counts or mark sources changed: the index worker does the
provider work, so nothing here reaches a provider.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import RequirementNotFoundError
from smb_requirement_agent.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.application.ports.corpus_membership import (
    CorpusActionsPort,
    CorpusMembershipPort,
    SourceChangesPort,
)
from smb_requirement_agent.application.ports.notifications import NotificationRepositoryPort
from smb_requirement_agent.application.ports.requirement_knowledge import (
    RequirementKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.requirement_indexing import IndexBacklogReader
from smb_requirement_agent.domain.jobs.entities import (
    ActorNotification,
    NotificationId,
    NotificationKind,
)
from smb_requirement_agent.domain.knowledge.errors import CorpusMembershipConflictError
from smb_requirement_agent.domain.knowledge.membership import (
    CorpusAction,
    CorpusActionKind,
    CorpusMembership,
    CorpusState,
    corpus_reason,
)
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.requirement.value_objects import RequirementStatus
from smb_requirement_agent.domain.shared.actors import (
    ActorId,
    ActorSnapshot,
)
from smb_requirement_agent.domain.shared.identifiers import RequirementId

# At most this many Requirements in one reindex.
REINDEX_MAX = 500

_REBUILD = (
    "The embedding model changed, so the whole index must be rebuilt first "
    "(the operator command `llm rebuild`)."
)


def _day(at: datetime) -> str:
    return f"{at.day} {at:%b %Y}"


@dataclass(frozen=True)
class MembershipResult:
    requirement_id: str
    state: CorpusState
    changed_at: datetime
    # Findings closed as "source retired"; none on reinstatement.
    closed_findings: int
    # The owner told of it, by display name; None when the Requirement has no owner.
    notified: str | None


@dataclass(frozen=True)
class BulkResult:
    # Requirements retried or marked for indexing again.
    requirements: int


class _CorpusAction:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        access: AccessRepositoryPort,
        knowledge: RequirementKnowledgeRepositoryPort,
        membership: CorpusMembershipPort,
        actions: CorpusActionsPort,
        notifications: NotificationRepositoryPort,
        transactions: TransactionManagerPort,
        clock: ClockPort,
    ) -> None:
        self._requirements = requirements
        self._access = access
        self._knowledge = knowledge
        self._membership = membership
        self._actions = actions
        self._notifications = notifications
        self._transactions = transactions
        self._clock = clock

    def _require(self, requirement_id: RequirementId) -> Requirement:
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        return requirement

    def _notify(
        self, requirement: Requirement, kind: NotificationKind, message: str, at: datetime
    ) -> str | None:
        access = self._access.get_requirement(requirement.id)
        if access is None or access.owner is None:
            return None
        owner = access.owner.actor
        self._notifications.add(
            ActorNotification(
                NotificationId(str(uuid.uuid4())),
                owner.id,
                None,
                kind,
                message,
                at,
                f"/requirements/{requirement.id.value}/knowledge",
            )
        )
        return owner.display_name

    def _record(
        self,
        kind: CorpusActionKind,
        requirement_ids: tuple[RequirementId, ...],
        actor: ActorSnapshot,
        reason: str | None,
        at: datetime,
    ) -> None:
        self._actions.add(CorpusAction(str(uuid.uuid4()), kind, requirement_ids, actor, reason, at))


class RetireFromCorpus(_CorpusAction):
    """Take a Requirement out of the corpus, with a reason; close the findings that cite it."""

    def execute(
        self, requirement_id: str, actor_id: str, actor_name: str, reason: str
    ) -> MembershipResult:
        cleaned = corpus_reason(reason)
        actor = ActorSnapshot(ActorId(actor_id), actor_name)
        subject = RequirementId(requirement_id)
        with self._transactions.transaction():
            requirement = self._require(subject)
            if requirement.status is RequirementStatus.DUPLICATE:
                raise CorpusMembershipConflictError(
                    "This Requirement is closed as a duplicate, so it is already out of the corpus."
                )
            findings = [
                item for item in self._knowledge.list_related_findings(subject) if item.actionable
            ]
            involved = {subject}
            for item in findings:
                involved.update((item.subject_requirement_id, item.related_requirement_id))
            for locked in sorted(involved, key=lambda value: value.value):
                self._transactions.lock_requirement(locked)
            current = self._membership.get(subject)
            if current is not None and current.retired:
                raise CorpusMembershipConflictError(
                    f"{current.actor.display_name} already retired it on "
                    f"{_day(current.changed_at)}."
                )
            now = self._clock.now()
            self._membership.save(
                CorpusMembership(subject, CorpusState.RETIRED, cleaned, actor, now)
            )
            # Read again under the locks: a decision may have landed since.
            closed = 0
            for item in self._knowledge.list_related_findings(subject):
                if item.actionable:
                    self._knowledge.save_finding(
                        item.close_source_retired(actor, cleaned, now), item.version
                    )
                    closed += 1
            notified = self._notify(
                requirement,
                NotificationKind.KNOWLEDGE_CORPUS_RETIRED,
                f"{actor_name} retired ‘{requirement.title.value}’ from the knowledge corpus: "
                f"{cleaned}",
                now,
            )
            self._record(CorpusActionKind.RETIRE, (subject,), actor, cleaned, now)
        return MembershipResult(subject.value, CorpusState.RETIRED, now, closed, notified)


class ReinstateToCorpus(_CorpusAction):
    """Return a retired Requirement to the corpus; it is indexed again and screened afresh."""

    def execute(
        self, requirement_id: str, actor_id: str, actor_name: str, reason: str
    ) -> MembershipResult:
        cleaned = corpus_reason(reason)
        actor = ActorSnapshot(ActorId(actor_id), actor_name)
        subject = RequirementId(requirement_id)
        with self._transactions.transaction():
            requirement = self._require(subject)
            self._transactions.lock_requirement(subject)
            current = self._membership.get(subject)
            if current is None or not current.retired:
                raise CorpusMembershipConflictError("This Requirement is not retired.")
            now = self._clock.now()
            self._membership.save(
                CorpusMembership(subject, CorpusState.ACTIVE, cleaned, actor, now)
            )
            notified = self._notify(
                requirement,
                NotificationKind.KNOWLEDGE_CORPUS_REINSTATED,
                f"{actor_name} returned ‘{requirement.title.value}’ to the knowledge corpus: "
                f"{cleaned}. Open its Knowledge step to screen it again.",
                now,
            )
            self._record(CorpusActionKind.REINSTATE, (subject,), actor, cleaned, now)
        return MembershipResult(subject.value, CorpusState.ACTIVE, now, 0, notified)


class BulkReindexRequirements:
    """Retry what stopped indexing, or index chosen Requirements again."""

    def __init__(
        self,
        backlog: IndexBacklogReader,
        source_changes: SourceChangesPort,
        actions: CorpusActionsPort,
        transactions: TransactionManagerPort,
        clock: ClockPort,
    ) -> None:
        self._backlog = backlog
        self._source_changes = source_changes
        self._actions = actions
        self._transactions = transactions
        self._clock = clock

    def retry_failed(self, actor_id: str, actor_name: str, reason: str | None) -> BulkResult:
        actor = ActorSnapshot(ActorId(actor_id), actor_name)
        now = self._clock.now()
        with self._transactions.transaction():
            retried = self._backlog.retry_failed(now)
            if retried is None:
                raise CorpusMembershipConflictError(_REBUILD)
            self._actions.add(
                CorpusAction(
                    str(uuid.uuid4()),
                    CorpusActionKind.RETRY,
                    tuple(RequirementId(item) for item in retried),
                    actor,
                    reason,
                    now,
                )
            )
        return BulkResult(len(retried))

    def reindex(
        self,
        requirement_ids: tuple[str, ...],
        actor_id: str,
        actor_name: str,
        reason: str | None,
    ) -> BulkResult:
        chosen = tuple(RequirementId(item) for item in dict.fromkeys(requirement_ids))
        if not chosen:
            raise CorpusMembershipConflictError("Choose at least one Requirement to reindex.")
        if len(chosen) > REINDEX_MAX:
            raise CorpusMembershipConflictError(
                f"Reindex at most {REINDEX_MAX} Requirements at a time."
            )
        actor = ActorSnapshot(ActorId(actor_id), actor_name)
        now = self._clock.now()
        with self._transactions.transaction():
            if self._backlog.pending() is None:
                raise CorpusMembershipConflictError(_REBUILD)
            marked = self._source_changes.mark_changed(chosen)
            self._actions.add(
                CorpusAction(
                    str(uuid.uuid4()), CorpusActionKind.REINDEX, chosen, actor, reason, now
                )
            )
        return BulkResult(marked)
