"""The Requirement corpus, its findings and nudges, for knowledge admins (Knowledge Center B2).

knowledge-portal reads these over the service-token internal API and keeps nothing. Rows carry
identity and state, plus each finding's rationale (requirement-portal ADR-0099, Amendment 1):
never a description, a passage or an evidence excerpt. Decisions stay with the owners; an admin
can only ask them to decide, at most once a week per finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import KnowledgeFindingNotFoundError
from smb_requirement_agent.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.application.ports.knowledge_portfolio import (
    CorpusQuery,
    FindingAge,
    FindingNudge,
    FindingNudgesPort,
    FindingQuery,
    FindingSide,
    IndexState,
    KnowledgePortfolioPort,
    NudgeMark,
    PersonName,
    RetiredMark,
    finding_age,
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
from smb_requirement_agent.domain.identity.entities import ActorId
from smb_requirement_agent.domain.jobs.entities import (
    ActorNotification,
    NotificationId,
    NotificationKind,
)
from smb_requirement_agent.domain.knowledge.entities import (
    KnowledgeFindingId,
    KnowledgeRelationshipKind,
)
from smb_requirement_agent.domain.knowledge.errors import KnowledgeFindingConflictError
from smb_requirement_agent.domain.requirement.value_objects import RequirementId

# A finding is nudged at most once in this long.
NUDGE_COOLDOWN = timedelta(days=7)


@dataclass(frozen=True)
class CorpusRow:
    requirement_id: str
    title: str
    # Closed as a duplicate: kept in the corpus with no passages.
    duplicate: bool
    owner: PersonName | None
    index_state: IndexState
    last_screened_at: datetime | None
    open_findings: int
    # Retired from the corpus by a knowledge admin (B3): when, by whom and why.
    retired: RetiredMark | None


@dataclass(frozen=True)
class CorpusPage:
    items: tuple[CorpusRow, ...]
    next_offset: int | None


@dataclass(frozen=True)
class FindingRow:
    finding_id: str
    kind: KnowledgeRelationshipKind
    # The screening judge's one line on why; never the evidence it cites.
    rationale: str
    raised_at: datetime
    age: FindingAge
    subject: FindingSide
    related: FindingSide
    last_nudge: NudgeMark | None
    # When it may be nudged again; None when it may be nudged now.
    next_nudge_at: datetime | None


@dataclass(frozen=True)
class FindingsPage:
    items: tuple[FindingRow, ...]
    next_offset: int | None


@dataclass(frozen=True)
class NudgeResult:
    finding_id: str
    nudged_at: datetime
    # The owners notified, by display name.
    recipients: tuple[str, ...]
    next_nudge_at: datetime


def _day(at: datetime) -> str:
    return f"{at.day} {at:%b %Y}"


def _next_nudge(last: datetime | None, now: datetime) -> datetime | None:
    if last is None or now - last >= NUDGE_COOLDOWN:
        return None
    return last + NUDGE_COOLDOWN


class KnowledgePortfolio:
    """The corpus and its findings, row by row."""

    def __init__(
        self,
        portfolio: KnowledgePortfolioPort,
        backlog: IndexBacklogReader,
        clock: ClockPort,
    ) -> None:
        self._portfolio = portfolio
        self._backlog = backlog
        self._clock = clock

    def corpus(
        self,
        *,
        index_state: IndexState | None,
        owner_id: str | None,
        text: str,
        open_findings_only: bool,
        not_screened_for_days: int | None,
        offset: int,
        limit: int,
        retired_only: bool = False,
    ) -> CorpusPage:
        pending = self._backlog.pending()
        # An index-state filter never lists a retired Requirement: it has left the corpus.
        retired = self._backlog.retired() if index_state is not None else frozenset[str]()
        if pending is None:
            # Until the rebuild, every Requirement waits for it; no other state applies.
            if index_state not in (None, IndexState.REBUILD_REQUIRED):
                return CorpusPage((), None)
            only, excluding = None, retired
        elif index_state is IndexState.CURRENT:
            only, excluding = None, frozenset(pending) | retired
        elif index_state in (IndexState.WAITING, IndexState.FAILED):
            stopped = index_state is IndexState.FAILED
            only, excluding = frozenset(k for k, v in pending.items() if v is stopped), frozenset()
        elif index_state is IndexState.REBUILD_REQUIRED:
            return CorpusPage((), None)
        else:
            only, excluding = None, frozenset()
        since = (
            self._clock.now() - timedelta(days=not_screened_for_days)
            if not_screened_for_days is not None
            else None
        )
        query = CorpusQuery(
            owner_id, text.strip(), open_findings_only, since, only, excluding, retired_only
        )
        entries = self._portfolio.corpus(query, offset, limit + 1)

        def state(requirement_id: str) -> IndexState:
            if pending is None:
                return IndexState.REBUILD_REQUIRED
            if requirement_id not in pending:
                return IndexState.CURRENT
            return IndexState.FAILED if pending[requirement_id] else IndexState.WAITING

        rows = tuple(
            CorpusRow(
                item.requirement_id,
                item.title,
                item.duplicate,
                item.owner,
                state(item.requirement_id),
                item.last_screened_at,
                item.open_findings,
                item.retired,
            )
            for item in entries[:limit]
        )
        return CorpusPage(rows, offset + limit if len(entries) > limit else None)

    def findings(
        self,
        *,
        kind: KnowledgeRelationshipKind | None,
        age: FindingAge | None,
        owner_id: str | None,
        offset: int,
        limit: int,
    ) -> FindingsPage:
        now = self._clock.now()
        query = FindingQuery(now, kind.value if kind else None, age, owner_id)
        entries = self._portfolio.findings(query, offset, limit + 1)
        rows = tuple(
            FindingRow(
                item.finding_id,
                KnowledgeRelationshipKind(item.kind),
                item.rationale,
                item.raised_at,
                finding_age(now - item.raised_at),
                item.subject,
                item.related,
                item.last_nudge,
                _next_nudge(item.last_nudge.at if item.last_nudge else None, now),
            )
            for item in entries[:limit]
        )
        return FindingsPage(rows, offset + limit if len(entries) > limit else None)


class NudgeFindingOwners:
    """Ask both Requirements' owners to decide a finding; recorded, and at most weekly."""

    def __init__(
        self,
        knowledge: RequirementKnowledgeRepositoryPort,
        requirements: RequirementRepositoryPort,
        access: AccessRepositoryPort,
        notifications: NotificationRepositoryPort,
        nudges: FindingNudgesPort,
        transactions: TransactionManagerPort,
        clock: ClockPort,
    ) -> None:
        self._knowledge = knowledge
        self._requirements = requirements
        self._access = access
        self._notifications = notifications
        self._nudges = nudges
        self._transactions = transactions
        self._clock = clock

    def execute(self, finding_id: str, actor_id: str, actor_name: str) -> NudgeResult:
        with self._transactions.transaction():
            finding = self._knowledge.get_finding(KnowledgeFindingId(finding_id))
            if finding is None:
                raise KnowledgeFindingNotFoundError(f"Knowledge finding {finding_id!r} not found.")
            subject = self._requirements.get(finding.subject_requirement_id)
            related = self._requirements.get(finding.related_requirement_id)
            if (
                not finding.actionable
                or subject is None
                or related is None
                or subject.version.value != finding.subject_version
                or related.version.value != finding.related_version
            ):
                raise KnowledgeFindingConflictError(
                    "This finding is no longer open: its owners have decided it, or a "
                    "Requirement has changed since it was raised."
                )
            for requirement_id in sorted(
                (finding.subject_requirement_id, finding.related_requirement_id),
                key=lambda item: item.value,
            ):
                self._transactions.lock_requirement(requirement_id)
            now = self._clock.now()
            latest = self._nudges.latest(finding_id)
            waiting = _next_nudge(latest.nudged_at if latest else None, now)
            if latest is not None and waiting is not None:
                raise KnowledgeFindingConflictError(
                    f"Its owners were asked on {_day(latest.nudged_at)}; "
                    f"it can be nudged again from {_day(waiting)}."
                )
            owners = self._owners(finding.subject_requirement_id, finding.related_requirement_id)
            if not owners:
                raise KnowledgeFindingConflictError("Neither Requirement has an owner to ask.")
            kind = (
                "a possible duplicate"
                if finding.kind is KnowledgeRelationshipKind.POSSIBLE_DUPLICATE
                else "a possible contradiction"
            )
            for owner_id, _, requirement_id in owners:
                self._notifications.add(
                    ActorNotification(
                        NotificationId(str(uuid4())),
                        ActorId(owner_id),
                        None,
                        NotificationKind.KNOWLEDGE_FINDINGS_NUDGE,
                        f"{actor_name} asks you to decide {kind} between "
                        f"‘{subject.title.value}’ and ‘{related.title.value}’.",
                        now,
                        f"/requirements/{requirement_id.value}/knowledge",
                    )
                )
            self._nudges.add(
                FindingNudge(
                    str(uuid4()),
                    finding_id,
                    actor_id,
                    actor_name,
                    now,
                    tuple(owner_id for owner_id, _, _ in owners),
                )
            )
        return NudgeResult(
            finding_id, now, tuple(name for _, name, _ in owners), now + NUDGE_COOLDOWN
        )

    def _owners(self, *requirement_ids: RequirementId) -> list[tuple[str, str, RequirementId]]:
        """Each distinct owner once, with the Requirement whose Knowledge step they open."""
        owners: dict[str, tuple[str, str, RequirementId]] = {}
        for requirement_id in requirement_ids:
            access = self._access.get_requirement(requirement_id)
            if access is not None and access.owner is not None:
                actor = access.owner.actor
                owners.setdefault(
                    actor.id.value, (actor.id.value, actor.display_name, requirement_id)
                )
        return list(owners.values())
