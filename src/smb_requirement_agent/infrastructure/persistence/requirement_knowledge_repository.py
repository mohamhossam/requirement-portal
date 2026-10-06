"""In-memory requirement knowledge index and review repository."""

from __future__ import annotations

import math
import re
import threading
from copy import deepcopy
from datetime import datetime
from typing import Any

from smb_requirement_agent.application.errors import KnowledgeGenerationError
from smb_requirement_agent.application.ports.requirement_knowledge import Embedding
from smb_requirement_agent.domain.knowledge.entities import (
    AnswerSuggestionSet,
    KnowledgeChunk,
    KnowledgeFinding,
    KnowledgeFindingId,
    KnowledgeMatch,
    KnowledgeScreen,
)
from smb_requirement_agent.domain.knowledge.errors import KnowledgeFindingConflictError
from smb_requirement_agent.domain.requirement.value_objects import RequirementId

_WORDS = re.compile(r"[a-z0-9]+")


class InMemoryRequirementKnowledgeStore:
    def __init__(self, lock: threading.RLock) -> None:
        self._fingerprints: dict[RequirementId, str] = {}
        self._chunks: dict[str, tuple[KnowledgeChunk, Embedding]] = {}
        self._screens: dict[RequirementId, list[KnowledgeScreen]] = {}
        self._findings: dict[KnowledgeFindingId, KnowledgeFinding] = {}
        self._suggestions: dict[tuple[RequirementId, str], list[AnswerSuggestionSet]] = {}

        self._dirty_sources: dict[RequirementId, int] = {}
        self._source_changes: dict[RequirementId, int] = {}
        self._index_lock = lock

    def snapshot_state(self) -> Any:
        return deepcopy(
            (
                self._fingerprints,
                self._chunks,
                self._screens,
                self._findings,
                self._suggestions,
                self._dirty_sources,
                self._source_changes,
            )
        )

    def restore_state(self, state: Any) -> None:
        (
            self._fingerprints,
            self._chunks,
            self._screens,
            self._findings,
            self._suggestions,
            self._dirty_sources,
            self._source_changes,
        ) = deepcopy(state)

    def indexed_fingerprint(self, requirement_id: RequirementId) -> str | None:
        return self._fingerprints.get(requirement_id)

    def mark_source_changed(self, requirement_id: RequirementId) -> None:
        with self._index_lock:
            change = self._source_changes.get(requirement_id, 0) + 1
            self._source_changes[requirement_id] = change
            self._dirty_sources[requirement_id] = change

    def source_versions(self) -> tuple[tuple[RequirementId, int], ...]:
        with self._index_lock:
            return tuple(sorted(self._source_changes.items(), key=lambda item: item[0].value))

    def pending_sources(self, limit: int, after: str = "") -> tuple[tuple[RequirementId, int], ...]:
        with self._index_lock:
            return tuple(
                sorted(
                    (
                        (key, value)
                        for key, value in self._dirty_sources.items()
                        if key.value > after
                    ),
                    key=lambda item: item[0].value,
                )[:limit]
            )

    def replace_if_current(
        self,
        requirement_id: RequirementId,
        expected_change: int,
        corpus_fingerprint: str,
        chunks: tuple[KnowledgeChunk, ...],
        embeddings: tuple[Embedding, ...],
    ) -> bool:
        with self._index_lock:
            if self._dirty_sources.get(requirement_id) != expected_change:
                return False
            self.replace(requirement_id, corpus_fingerprint, chunks, embeddings)
            del self._dirty_sources[requirement_id]
            return True

    def replace(
        self,
        requirement_id: RequirementId,
        corpus_fingerprint: str,
        chunks: tuple[KnowledgeChunk, ...],
        embeddings: tuple[Embedding, ...],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise KnowledgeGenerationError("Each knowledge chunk requires one embedding.")
        if any(len(embedding) != 768 for embedding in embeddings):
            raise KnowledgeGenerationError(
                "Knowledge embeddings must contain exactly 768 dimensions."
            )
        self._chunks = {
            key: value
            for key, value in self._chunks.items()
            if value[0].requirement_id != requirement_id
        }
        self._chunks.update(
            {
                chunk.id.value: (chunk, embedding)
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            }
        )
        self._fingerprints[requirement_id] = corpus_fingerprint

    def search(
        self,
        query_text: str,
        query_embedding: Embedding,
        exclude_requirement_id: RequirementId | None,
        limit: int,
    ) -> tuple[KnowledgeMatch, ...]:
        terms = set(_WORDS.findall(query_text.casefold()))
        candidates = [
            value
            for value in self._chunks.values()
            if value[0].requirement_id != exclude_requirement_id
        ]
        lexical = sorted(
            candidates,
            key=lambda value: len(terms.intersection(_WORDS.findall(value[0].text.casefold()))),
            reverse=True,
        )
        semantic = sorted(
            candidates,
            key=lambda value: _cosine(query_embedding, value[1]),
            reverse=True,
        )
        lexical_rank = {item[0].id.value: rank for rank, item in enumerate(lexical, 1)}
        semantic_rank = {item[0].id.value: rank for rank, item in enumerate(semantic, 1)}
        fused = [
            KnowledgeMatch(
                chunk,
                lexical_rank.get(chunk.id.value),
                semantic_rank.get(chunk.id.value),
                1 / (60 + lexical_rank[chunk.id.value]) + 1 / (60 + semantic_rank[chunk.id.value]),
            )
            for chunk, _ in candidates
        ]
        return tuple(sorted(fused, key=lambda item: item.fused_score, reverse=True)[:limit])

    def get_chunks(self, chunk_ids: tuple[str, ...]) -> tuple[KnowledgeChunk, ...]:
        return tuple(self._chunks[item][0] for item in chunk_ids if item in self._chunks)

    def append_screen(
        self, screen: KnowledgeScreen, findings: tuple[KnowledgeFinding, ...]
    ) -> None:
        self._screens.setdefault(screen.requirement_id, []).append(screen)
        for finding in findings:
            self._findings[finding.id] = finding

    def current_screen(self, requirement_id: RequirementId) -> KnowledgeScreen | None:
        values = self._screens.get(requirement_id, [])
        return values[-1] if values else None

    def get_finding(self, finding_id: KnowledgeFindingId) -> KnowledgeFinding | None:
        return self._findings.get(finding_id)

    def list_findings(self, screen_id: str) -> tuple[KnowledgeFinding, ...]:
        return tuple(item for item in self._findings.values() if item.screen_id.value == screen_id)

    def save_finding(self, finding: KnowledgeFinding, expected_version: int) -> None:
        current = self._findings.get(finding.id)
        if current is None or current.version != expected_version:
            raise KnowledgeFindingConflictError(
                "The knowledge finding changed since it was loaded. Refresh and try again."
            )
        self._findings[finding.id] = finding
        self.mark_source_changed(finding.subject_requirement_id)
        self.mark_source_changed(finding.related_requirement_id)

    def raised_findings(self) -> tuple[tuple[KnowledgeFinding, datetime], ...]:
        """Every finding with the time its screen raised it; for the corpus summary."""
        with self._index_lock:
            raised = {
                finding_id: screen.provenance.generated_at
                for screens in self._screens.values()
                for screen in screens
                for finding_id in screen.finding_ids
            }
            return tuple(
                (finding, raised[finding.id])
                for finding in self._findings.values()
                if finding.id in raised
            )

    def list_related_findings(self, requirement_id: RequirementId) -> tuple[KnowledgeFinding, ...]:
        return tuple(
            item
            for item in self._findings.values()
            if requirement_id in (item.subject_requirement_id, item.related_requirement_id)
        )

    def append_suggestion_set(self, suggestions: AnswerSuggestionSet) -> None:
        key = (suggestions.requirement_id, suggestions.question_id.value)
        self._suggestions.setdefault(key, []).append(suggestions)

    def latest_suggestion_set(
        self, requirement_id: RequirementId, question_id: str
    ) -> AnswerSuggestionSet | None:
        values = self._suggestions.get((requirement_id, question_id), [])
        return values[-1] if values else None


def _cosine(left: Embedding, right: Embedding) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    denominator = math.sqrt(sum(item * item for item in left)) * math.sqrt(
        sum(item * item for item in right)
    )
    return numerator / denominator if denominator else 0.0
