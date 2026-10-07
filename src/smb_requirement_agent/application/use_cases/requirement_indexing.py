"""Incremental Requirement indexing, independent of screening and generation."""

import hashlib
import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from uuid import uuid4

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import KnowledgeGenerationError, ModelTransportError
from smb_requirement_agent.application.ports.corpus_membership import CorpusMembershipPort
from smb_requirement_agent.application.ports.requirement_indexing import (
    FAILED_AFTER,
    RequirementIndexProgressPort,
)
from smb_requirement_agent.application.ports.requirement_knowledge import (
    KnowledgeEmbeddingPort,
    RequirementKnowledgeIndexPort,
)
from smb_requirement_agent.application.use_cases.identity_access import RequirementAccessService
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    RequirementKnowledgeCorpus,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True)
class IndexBacklog:
    """What the index has still to do: counts only, never which Requirements."""

    waiting: int
    failed: int
    # The embedding model changed and the new index has not been built yet.
    rebuild_required: bool


@dataclass(frozen=True)
class RequirementIndexStatus:
    state: str
    completed_chunks: int = 0
    total_chunks: int = 0
    retryable: bool = False


class IndexBacklogReader:
    """What the index has still to do, read without the embedding provider."""

    def __init__(
        self,
        index: RequirementKnowledgeIndexPort,
        progress: RequirementIndexProgressPort,
        identity: str,
        membership: CorpusMembershipPort | None = None,
    ) -> None:
        self._index, self._progress, self._identity = index, progress, identity
        self._membership = membership

    def retired(self) -> frozenset[str]:
        """Requirements retired from the corpus: no index state applies to them (B3)."""
        return frozenset(self._membership.retired()) if self._membership else frozenset()

    def backlog(self) -> IndexBacklog:
        """Sources still to index; one is failed once it stopped retrying on its current change."""
        pending = self.pending()
        if pending is None:
            return IndexBacklog(0, 0, rebuild_required=True)
        failed = sum(1 for stopped in pending.values() if stopped)
        return IndexBacklog(len(pending) - failed, failed, rebuild_required=False)

    def retry_failed(self, now: datetime) -> tuple[str, ...] | None:
        """Retry every source that stopped retrying; None while a rebuild waits.

        Only the failure count is reset; the worker picks them up and does the provider work.
        """
        pending = self.pending()
        if pending is None:
            return None
        return tuple(
            source
            for source, stopped in sorted(pending.items())
            if stopped and self._progress.retry(self._identity, source, now)
        )

    def pending(self) -> dict[str, bool] | None:
        """Each source still to index, True when it stopped retrying; None when a rebuild waits."""
        stopped = dict(self._progress.failed(self._identity))
        retired = self.retired()
        pending: dict[str, bool] = {}
        after = ""
        try:
            while page := self._index.pending_sources(500, after):
                for source, change in page:
                    # A retired source only waits to drop its passages; it is not indexing work.
                    if source.value not in retired:
                        pending[source.value] = stopped.get(source.value) == change
                after = page[-1][0].value
        except ModelTransportError:
            return None
        return pending


class IndexRequirementKnowledge:
    """One provider batch per turn; partial vectors never become searchable."""

    def __init__(
        self,
        corpus: RequirementKnowledgeCorpus,
        index: RequirementKnowledgeIndexPort,
        embeddings: KnowledgeEmbeddingPort,
        progress: RequirementIndexProgressPort,
        clock: ClockPort,
        identity: str,
        access: RequirementAccessService,
    ) -> None:
        self._corpus, self._index, self._embeddings = corpus, index, embeddings
        self._progress, self._clock, self.identity = progress, clock, identity
        self._access = access
        self._cursor = ""

    def ready(self) -> bool:
        try:
            return not self._index.pending_sources(1)
        except ModelTransportError:
            return False

    def status(self, source: str, actor: ActorProfile) -> RequirementIndexStatus:
        self._access.require_requirement_member(RequirementId(source), actor)
        if self.ready():
            return RequirementIndexStatus("ready")
        try:
            self._index.pending_sources(1)
        except ModelTransportError:
            return RequirementIndexStatus("rebuild_required")
        progress = self._progress.get(self.identity, source)
        return RequirementIndexStatus(
            "failed" if progress.failures >= FAILED_AFTER else "indexing",
            progress.completed,
            progress.total,
            progress.failures >= FAILED_AFTER,
        )

    def retry(self, source: str, actor: ActorProfile) -> None:
        self._access.require_requirement_member(RequirementId(source), actor)
        self._progress.retry(self.identity, source, self._clock.now())

    def process_next(self) -> bool:
        try:
            pending = self._index.pending_sources(100, self._cursor)
            if not pending:
                self._cursor = ""
                pending = self._index.pending_sources(100)
        except ModelTransportError:
            return False  # Explicit generation rebuild is required after a model change.
        for source, change in pending:
            self._cursor = source.value
            now, token = self._clock.now(), str(uuid4())
            progress = self._progress.claim(
                self.identity,
                source.value,
                change,
                token,
                now,
                now + timedelta(minutes=15),
            )
            if progress is None:
                continue
            try:
                chunks, fingerprint = self._corpus.index_source(source)
                keys = tuple(hashlib.sha256(c.text.encode()).hexdigest() for c in chunks)
                cache = dict(progress.vectors)
                missing = tuple(dict.fromkeys(k for k in keys if k not in cache))[:16]
                texts = {k: c.text for k, c in zip(keys, chunks, strict=True)}
                if missing:
                    vectors = self._embeddings.embed(tuple(texts[k] for k in missing))
                    if len(vectors) != len(missing) or any(
                        len(v) != 768
                        or not all(math.isfinite(x) for x in v)
                        or not any(x != 0 for x in v)
                        for v in vectors
                    ):
                        raise KnowledgeGenerationError(
                            "Embedding provider returned incomplete batch."
                        )
                    cache.update(zip(missing, vectors, strict=True))
                updated = replace(
                    progress,
                    failures=0,
                    retry_at=None,
                    vectors=tuple((k, cache[k]) for k in dict.fromkeys(keys) if k in cache),
                    completed=sum(k in cache for k in keys),
                    total=len(keys),
                )
                # Persist the batch under a live lease before attempting source-version CAS.
                if self._progress.save(
                    self.identity, source.value, token, updated, self._clock.now()
                ):
                    if updated.completed == updated.total:
                        self._index.replace_if_current(
                            source,
                            change,
                            fingerprint,
                            chunks,
                            tuple(cache[k] for k in keys),
                        )
                return True
            except (KnowledgeGenerationError, ModelTransportError):
                failed = replace(
                    progress,
                    failures=progress.failures + 1,
                    retry_at=self._clock.now() + timedelta(seconds=30 * 2**progress.failures),
                )
                self._progress.save(self.identity, source.value, token, failed, self._clock.now())
                return True
        return False
