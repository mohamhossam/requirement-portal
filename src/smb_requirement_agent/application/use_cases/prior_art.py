"""Prior art: which delivered historic requirements a Requirement resembles (ADR-0102).

A check searches the historic corpus with the Requirement's screening text, then asks the
prior-art judge which of the closest historic requirements delivered the same capability.
It is informational: it is never a finding, never counts toward knowledge readiness and
never blocks confirmation. It runs as an automatic job, after everything else waiting, and
within an hourly budget of judge calls.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    KnowledgeGenerationError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.embedding import KnowledgeEmbeddingPort
from smb_requirement_agent.application.ports.historic_corpus import (
    HistoricCorpusIndexPort,
    HistoricMatch,
    HistoricRequirementStatePort,
)
from smb_requirement_agent.application.ports.knowledge_access import KnowledgeAccessPort
from smb_requirement_agent.application.ports.prior_art import (
    HistoricCitation,
    PriorArtBudgetPort,
    PriorArtCandidateInput,
    PriorArtEvidenceInput,
    PriorArtJudgement,
    PriorArtJudgePort,
    PriorArtRepositoryPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    RequirementKnowledgeCorpus,
)
from smb_requirement_agent.domain.knowledge.bounded_text import bounded_knowledge_text
from smb_requirement_agent.domain.knowledge.historic import WORK_ITEM_TYPES, HistoricSourceKind
from smb_requirement_agent.domain.knowledge.prior_art import (
    MATCHES_MAX,
    PriorArtCheck,
    PriorArtEvidence,
    PriorArtMatch,
    PriorArtStatus,
    PriorArtVerdict,
)
from smb_requirement_agent.identity.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementPermission,
)
from smb_requirement_agent.jobs.application.ports.ai_jobs import (
    AiJobCommand,
    AiJobRecord,
    AiJobRepositoryPort,
    JsonValue,
)
from smb_requirement_agent.jobs.application.use_cases.command_fingerprint import command_fingerprint
from smb_requirement_agent.jobs.domain.entities import (
    AiJob,
    AiJobId,
    AiJobOperation,
    AiJobOrigin,
    AiJobStatus,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.domain.requirement.value_objects import RequirementStatus
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

# What the judge is shown: the closest historic requirements, a few passages each.
SEARCH_LIMIT = 100
CANDIDATES_MAX = MATCHES_MAX
EVIDENCE_PER_CANDIDATE = 4


class PriorArtBudgetSpentError(Exception):
    """This hour's prior-art judge calls are spent; the job waits for the next hour."""


@dataclass(frozen=True)
class PriorArtView:
    status: PriorArtStatus
    # What the current check would have to match; changes when the Requirement or the
    # historic corpus does, so a reader knows when to ask again.
    input_key: str
    check: PriorArtCheck | None


def _subject_key(subject_text: str, corpus_version: int) -> str:
    return f"{hashlib.sha256(subject_text.encode()).hexdigest()}:{corpus_version}"


def _where(match: HistoricMatch) -> str:
    evidence = match.chunk.evidence
    if match.chunk.source_kind is HistoricSourceKind.HISTORIC_BRD:
        return f"{evidence.get('brd_filename', '')}, {evidence.get('label', '')}"
    lineage = evidence.get("lineage")
    links = lineage if isinstance(lineage, list) else []
    return " › ".join(
        f"{WORK_ITEM_TYPES.get(str(link.get('type')), '')} #{link.get('id')} {link.get('title')}"
        for link in links
        if isinstance(link, dict)
    )


def _candidates(
    matches: tuple[HistoricMatch, ...],
) -> tuple[tuple[PriorArtCandidateInput, ...], dict[int, HistoricMatch]]:
    """The closest historic requirements, numbered, each with its best few passages."""
    grouped: dict[str, list[HistoricMatch]] = {}
    for match in matches:
        group = grouped.setdefault(match.chunk.historic_id, [])
        if len(group) < EVIDENCE_PER_CANDIDATE:
            group.append(match)
    ranked = sorted(grouped.values(), key=lambda group: group[0].fused_score, reverse=True)
    candidates: list[PriorArtCandidateInput] = []
    numbered: dict[int, HistoricMatch] = {}
    number = 0
    for position, group in enumerate(ranked[:CANDIDATES_MAX], start=1):
        evidence: list[PriorArtEvidenceInput] = []
        for match in group:
            number += 1
            numbered[number] = match
            evidence.append(PriorArtEvidenceInput(number, match.chunk.text, _where(match)))
        candidates.append(
            PriorArtCandidateInput(
                position, group[0].chunk.historic_id, group[0].title, tuple(evidence)
            )
        )
    return tuple(candidates), numbered


class ScreenPriorArt:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        corpus: RequirementKnowledgeCorpus,
        index: HistoricCorpusIndexPort,
        states: HistoricRequirementStatePort,
        checks: PriorArtRepositoryPort,
        embeddings: KnowledgeEmbeddingPort,
        judge: PriorArtJudgePort,
        budget: PriorArtBudgetPort,
        clock: ClockPort,
        transactions: TransactionManagerPort,
        *,
        authorization: KnowledgeAccessPort,
        identity: str,
        enabled: bool,
        judge_calls_per_hour: int,
    ) -> None:
        self._requirements = requirements
        self._corpus = corpus
        self._index = index
        self._states = states
        self._checks = checks
        self._embeddings = embeddings
        self._judge = judge
        self._budget = budget
        self._clock = clock
        self._transactions = transactions
        self._authorization = authorization
        self._identity = identity
        self._enabled = enabled
        self._judge_calls_per_hour = judge_calls_per_hour

    def execute(
        self, actor: ActorProfile, requirement_id: RequirementId, expected_key: str
    ) -> PriorArtCheck | None:
        """A member retrying a failed check."""
        with self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER):
            return self._execute(requirement_id, expected_key)

    def execute_automatic(
        self, requirement_id: RequirementId, expected_key: str
    ) -> PriorArtCheck | None:
        with self._authorization.automatic_mutation(
            requirement_id, AiJobOperation.SCREEN_PRIOR_ART
        ):
            return self._execute(requirement_id, expected_key)

    def _execute(self, requirement_id: RequirementId, expected_key: str) -> PriorArtCheck | None:
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        if (
            not self._enabled
            or requirement.status is RequirementStatus.DUPLICATE
            or self._corpus.retirement(requirement_id) is not None
        ):
            return None
        subject_text = self._corpus.subject_text(requirement_id)
        version = self._index.version()
        key = _subject_key(subject_text, version)
        if key != expected_key or not self._index.has_content(self._identity):
            return None  # Superseded by a newer job, or nothing to compare with yet.
        existing = self._checks.get(requirement_id)
        if existing is not None and existing.key() == key:
            return existing
        if self._budget.remaining(self._clock.now(), self._judge_calls_per_hour) <= 0:
            raise PriorArtBudgetSpentError("This hour's prior-art checks are spent.")
        with self._transactions.external_call():
            query = self._embeddings.embed((bounded_knowledge_text(subject_text)[0],))
            if len(query) != 1:
                raise KnowledgeGenerationError("Embedding provider returned no query embedding.")
            found = self._index.search(subject_text, query[0], self._identity, SEARCH_LIMIT)
        candidates, numbered = _candidates(found)
        judgements: tuple[PriorArtJudgement, ...] = ()
        if candidates:
            with self._transactions.external_call():
                judgements = self._judge.judge(requirement.title.value, subject_text, candidates)
        matches = _validated(judgements, candidates, numbered)
        check = PriorArtCheck(
            requirement_id,
            key.split(":", 1)[0],
            version,
            self._identity,
            Provenance(self._clock.now(), self._judge.model, self._judge.prompt_version),
            matches,
        )
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._budget.spend(self._clock.now())
            # A historic requirement withdrawn while the judge worked is not kept.
            standing = self._states.standing(tuple(m.historic_requirement_id for m in matches))
            kept = tuple(
                match
                for match in matches
                if (state := standing.get(match.historic_requirement_id)) is not None
                and state.published
            )
            check = PriorArtCheck(
                check.requirement_id,
                check.subject_fingerprint,
                check.corpus_version,
                check.embedding_identity,
                check.provenance,
                kept,
            )
            self._checks.replace(check)
        return check


def _validated(
    judgements: tuple[PriorArtJudgement, ...],
    candidates: tuple[PriorArtCandidateInput, ...],
    numbered: dict[int, HistoricMatch],
) -> tuple[PriorArtMatch, ...]:
    """The judge's answer, held to what it was shown; anything else is refused whole."""
    by_number = {candidate.number: candidate for candidate in candidates}
    if len(judgements) > MATCHES_MAX:
        raise KnowledgeGenerationError("Prior-art judge returned too many matches.")
    seen: set[int] = set()
    matches: list[PriorArtMatch] = []
    for judgement in judgements:
        candidate = by_number.get(judgement.candidate_number)
        if candidate is None or judgement.candidate_number in seen:
            raise KnowledgeGenerationError("Prior-art judge named a candidate it was not shown.")
        seen.add(judgement.candidate_number)
        own = {item.number for item in candidate.evidence}
        cited = tuple(dict.fromkeys(judgement.cited_evidence_numbers))
        if not cited or not set(cited) <= own or not judgement.rationale.strip():
            raise KnowledgeGenerationError(
                "Prior-art judge cited evidence outside its candidate, or gave no rationale."
            )
        first = numbered[cited[0]]
        matches.append(
            PriorArtMatch(
                candidate.historic_requirement_id,
                first.publication,
                first.title,
                PriorArtVerdict.SIMILAR_PAST_REQUIREMENT,
                judgement.rationale.strip(),
                tuple(
                    PriorArtEvidence(
                        numbered[number].chunk.chunk_id,
                        numbered[number].chunk.source_kind,
                        numbered[number].chunk.text,
                        dict(numbered[number].chunk.evidence),
                    )
                    for number in cited
                ),
            )
        )
    return tuple(matches)


class GetPriorArt:
    """Read-only: where a Requirement's prior art stands, and its matches still published."""

    def __init__(
        self,
        corpus: RequirementKnowledgeCorpus,
        index: HistoricCorpusIndexPort,
        states: HistoricRequirementStatePort,
        checks: PriorArtRepositoryPort,
        jobs: AiJobRepositoryPort,
        budget: PriorArtBudgetPort,
        clock: ClockPort,
        *,
        identity: str,
        enabled: bool,
        judge_calls_per_hour: int,
    ) -> None:
        self._corpus = corpus
        self._index = index
        self._states = states
        self._checks = checks
        self._jobs = jobs
        self._budget = budget
        self._clock = clock
        self._identity = identity
        self._enabled = enabled
        self._judge_calls_per_hour = judge_calls_per_hour

    def current_key(self, requirement_id: RequirementId) -> str:
        return _subject_key(self._corpus.subject_text(requirement_id), self._index.version())

    def execute(self, requirement_id: RequirementId) -> PriorArtView:
        if not self._enabled:
            return PriorArtView(PriorArtStatus.DISABLED, "", None)
        if not self._index.has_content(self._identity):
            return PriorArtView(PriorArtStatus.NO_HISTORIC_KNOWLEDGE, "", None)
        key = self.current_key(requirement_id)
        check = self._checks.get(requirement_id)
        if check is not None:
            standing = self._states.standing(
                tuple(match.historic_requirement_id for match in check.matches)
            )
            check = PriorArtCheck(
                check.requirement_id,
                check.subject_fingerprint,
                check.corpus_version,
                check.embedding_identity,
                check.provenance,
                tuple(
                    match
                    for match in check.matches
                    if (state := standing.get(match.historic_requirement_id)) is not None
                    and state.published
                ),
            )
        jobs = [
            record.job
            for record in self._jobs.list_for_requirement(requirement_id, limit=20)
            if record.job.operation is AiJobOperation.SCREEN_PRIOR_ART
        ]
        if any(not job.status.terminal for job in jobs):
            spent = self._budget.remaining(self._clock.now(), self._judge_calls_per_hour) <= 0
            return PriorArtView(
                PriorArtStatus.WAITING if spent else PriorArtStatus.CHECKING, key, check
            )
        if check is not None and check.key() == key:
            return PriorArtView(PriorArtStatus.CURRENT, key, check)
        latest = jobs[0] if jobs else None
        if latest is not None and latest.status is AiJobStatus.FAILED:
            return PriorArtView(PriorArtStatus.FAILED, key, check)
        return PriorArtView(
            PriorArtStatus.OUT_OF_DATE if check is not None else PriorArtStatus.NOT_CHECKED,
            key,
            check,
        )


class PriorArtScheduler:
    """Queue one automatic prior-art check per Requirement and key, never more."""

    def __init__(
        self,
        prior_art: GetPriorArt,
        checks: PriorArtRepositoryPort,
        index: HistoricCorpusIndexPort,
        jobs: AiJobRepositoryPort,
        requirements: RequirementRepositoryPort,
        clock: ClockPort,
        automatic_actor: ActorProfile,
        *,
        identity: str,
        enabled: bool,
    ) -> None:
        self._prior_art = prior_art
        self._checks = checks
        self._index = index
        self._jobs = jobs
        self._requirements = requirements
        self._clock = clock
        self._automatic_actor = automatic_actor
        self._identity = identity
        self._enabled = enabled

    def schedule(self, requirement_id: RequirementId) -> None:
        self._schedule(requirement_id)

    def ensure(self, requirement_id: RequirementId) -> None:
        self._schedule(requirement_id)

    def _schedule(self, requirement_id: RequirementId) -> None:
        if not self._enabled or not self._index.has_content(self._identity):
            return
        requirement = self._requirements.get(requirement_id)
        if requirement is None or requirement.status is RequirementStatus.DUPLICATE:
            return
        key = self._prior_art.current_key(requirement_id)
        check = self._checks.get(requirement_id)
        if check is not None and check.key() == key:
            return
        arguments: dict[str, JsonValue] = {"prior_art_key": key}
        command = AiJobCommand(arguments)
        operation = AiJobOperation.SCREEN_PRIOR_ART
        command_hash = command_fingerprint(requirement_id, operation, command)
        now = self._clock.now()
        job_id = AiJobId(str(uuid.uuid4()))
        job = AiJob(
            job_id,
            requirement_id,
            operation,
            AiJobStatus.QUEUED,
            self._automatic_actor.snapshot(),
            now,
            now,
            f"automatic:{requirement_id.value}:{operation.value}:{command_hash}:{job_id.value}",
            command_hash,
            origin=AiJobOrigin.AUTOMATIC,
        )
        # The same key is never queued twice, even after a failure: no mass re-screening.
        self._jobs.reserve_automatic(AiJobRecord(job, command))


class HistoricCitations:
    """Where each historic requirement is cited, for the knowledge portal (ADR-0102).

    Identity and state only, as the portfolio reads are: never a rationale or a passage.
    """

    def __init__(
        self,
        checks: PriorArtRepositoryPort,
        get_prior_art: GetPriorArt,
        requirements: RequirementRepositoryPort,
        access: AccessRepositoryPort,
        corpus: RequirementKnowledgeCorpus,
    ) -> None:
        self._checks = checks
        self._get_prior_art = get_prior_art
        self._requirements = requirements
        self._access = access
        self._corpus = corpus

    def counts(self, historic_ids: tuple[str, ...]) -> dict[str, int]:
        found = self._checks.citation_counts(historic_ids)
        return {historic_id: found.get(historic_id, 0) for historic_id in historic_ids}

    def page(
        self, historic_id: str, offset: int, limit: int
    ) -> tuple[tuple[HistoricCitation, ...], int | None]:
        ids = self._checks.citing(historic_id, offset, limit + 1)
        more = len(ids) > limit
        citations: list[HistoricCitation] = []
        for requirement_id in ids[:limit]:
            requirement = self._requirements.get(requirement_id)
            check = self._checks.get(requirement_id)
            if requirement is None or check is None:
                continue
            access = self._access.get_requirement(requirement_id)
            owner = access.owner.actor.display_name if access and access.owner else ""
            citations.append(
                HistoricCitation(
                    requirement_id.value,
                    requirement.title.value,
                    owner,
                    check.checked_at,
                    check.key() == self._get_prior_art.current_key(requirement_id),
                    self._corpus.retirement(requirement_id) is not None,
                    requirement.status is RequirementStatus.DUPLICATE,
                )
            )
        return tuple(citations), (offset + limit if more else None)


def checked_at(check: PriorArtCheck | None) -> datetime | None:
    return None if check is None else check.checked_at
