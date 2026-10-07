"""Prior art: the AI judge, the checks it leaves behind, and their schedule (ADR-0102)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from smb_requirement_agent.domain.knowledge.prior_art import PriorArtCheck
from smb_requirement_agent.domain.shared.identifiers import RequirementId


@dataclass(frozen=True)
class PriorArtEvidenceInput:
    """One numbered passage the judge may cite. Numbers run across every candidate."""

    number: int
    text: str
    # Where it is from, in words: "BRD-2025-014.docx, Paragraph 2" or "Epic #48213 › …".
    where: str


@dataclass(frozen=True)
class PriorArtCandidateInput:
    number: int
    historic_requirement_id: str
    title: str
    evidence: tuple[PriorArtEvidenceInput, ...]


@dataclass(frozen=True)
class PriorArtJudgement:
    candidate_number: int
    rationale: str
    cited_evidence_numbers: tuple[int, ...]


class PriorArtJudgePort(Protocol):
    """Judges which delivered historic requirements a new Requirement resembles.

    Similar means the same business capability or outcome, not a shared topic. It may
    answer that none is similar.
    """

    model: str
    prompt_version: str

    def judge(
        self, title: str, subject_text: str, candidates: tuple[PriorArtCandidateInput, ...]
    ) -> tuple[PriorArtJudgement, ...]: ...


@dataclass(frozen=True)
class HistoricCitation:
    """A Requirement whose current prior art cites a historic requirement."""

    requirement_id: str
    title: str
    owner: str
    checked_at: datetime
    current: bool
    retired: bool
    duplicate: bool


class PriorArtRepositoryPort(Protocol):
    def get(self, requirement_id: RequirementId) -> PriorArtCheck | None: ...

    def replace(self, check: PriorArtCheck) -> None:
        """Keep `check` as the Requirement's prior art, in place of any earlier one."""
        ...

    def citation_counts(self, historic_ids: tuple[str, ...]) -> dict[str, int]: ...

    def citing(self, historic_id: str, offset: int, limit: int) -> tuple[RequirementId, ...]:
        """Requirements whose kept check matches `historic_id`, oldest check first."""
        ...


class PriorArtBudgetPort(Protocol):
    """Prior-art judge calls, counted in hourly windows across the portal."""

    def spend(self, now: datetime) -> None:
        """Count one check this hour. The cap is held at claim time, before any call."""
        ...

    def remaining(self, now: datetime, hourly: int) -> int: ...


class PriorArtStorePort(PriorArtRepositoryPort, PriorArtBudgetPort, Protocol):
    """Checks and the judge's budget, kept together."""


class PriorArtSchedulerPort(Protocol):
    def schedule(self, requirement_id: RequirementId) -> None: ...

    def ensure(self, requirement_id: RequirementId) -> None: ...
