"""Isolated offline store for AI-proposed catalogue changes."""

from dataclasses import replace
from threading import RLock

from smb_requirement_agent.application.ports.catalogue_candidates import ExtractionRun
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateDecisionConflictError,
    CandidateStatus,
    CatalogueCandidate,
)


class InMemoryCatalogueCandidates:
    def __init__(self) -> None:
        self._lock = RLock()
        self._runs: list[ExtractionRun] = []
        self._candidates: dict[str, CatalogueCandidate] = {}

    def replace_proposals(
        self, run: ExtractionRun, candidates: tuple[CatalogueCandidate, ...]
    ) -> None:
        with self._lock:
            self._candidates = {
                key: item
                for key, item in self._candidates.items()
                if not (
                    item.release_id == run.release_id
                    and item.document_version_id == run.document_version_id
                    and item.status is CandidateStatus.PROPOSED
                )
            }
            self._candidates.update({item.id: item for item in candidates})
            self._runs.append(run)

    def runs(self, release_id: str) -> tuple[ExtractionRun, ...]:
        with self._lock:
            return tuple(item for item in self._runs if item.release_id == release_id)

    def list(self, release_id: str) -> tuple[CatalogueCandidate, ...]:
        with self._lock:
            return tuple(
                item for item in self._candidates.values() if item.release_id == release_id
            )

    def get(self, candidate_id: str) -> CatalogueCandidate | None:
        with self._lock:
            return self._candidates.get(candidate_id)

    def save_decision(self, candidate: CatalogueCandidate) -> None:
        with self._lock:
            current = self._candidates.get(candidate.id)
            if current is None or current.status is not CandidateStatus.PROPOSED:
                raise CandidateDecisionConflictError("This suggestion was already decided.")
            self._candidates[candidate.id] = candidate

    def reopen(self, candidate_id: str) -> None:
        with self._lock:
            current = self._candidates[candidate_id]
            self._candidates[candidate_id] = replace(
                current,
                status=CandidateStatus.PROPOSED,
                edited=False,
                decided_by=None,
                decided_at=None,
            )
