"""Prior art: delivered historic requirements a new Requirement resembles (ADR-0102).

A prior-art check is informational. It is never a finding: it never counts toward a
Requirement's knowledge readiness, never blocks confirmation, and never appears in
finding counts. Each match carries the AI judge's rationale and the passages it cited.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from smb_requirement_agent.references.domain.errors import InvalidKnowledgeError
from smb_requirement_agent.references.domain.historic import HistoricSourceKind
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

MATCHES_MAX = 5
EVIDENCE_MAX = 5


class PriorArtVerdict(StrEnum):
    SIMILAR_PAST_REQUIREMENT = "similar_past_requirement"


class PriorArtStatus(StrEnum):
    """Where a Requirement's prior art stands, as its reader is told."""

    DISABLED = "disabled"
    NO_HISTORIC_KNOWLEDGE = "no_historic_knowledge"
    NOT_CHECKED = "not_checked"
    CHECKING = "checking"
    WAITING = "waiting"
    CURRENT = "current"
    OUT_OF_DATE = "out_of_date"
    FAILED = "failed"


@dataclass(frozen=True)
class PriorArtEvidence:
    """What the judge cited, kept as it was read so a later change cannot alter it."""

    chunk_id: str
    source_kind: HistoricSourceKind
    excerpt: str
    # A passage's BRD and location, or a work item's lineage, Epic first.
    context: dict[str, object]


@dataclass(frozen=True)
class PriorArtMatch:
    historic_requirement_id: str
    publication: int
    title: str
    verdict: PriorArtVerdict
    rationale: str
    evidence: tuple[PriorArtEvidence, ...]

    def __post_init__(self) -> None:
        if not self.rationale.strip():
            raise InvalidKnowledgeError("A prior-art match needs the judge's rationale.")
        if not 1 <= len(self.evidence) <= EVIDENCE_MAX:
            raise InvalidKnowledgeError(f"A prior-art match cites 1 to {EVIDENCE_MAX} passages.")


@dataclass(frozen=True)
class PriorArtCheck:
    """One completed check of a Requirement against the historic corpus."""

    requirement_id: RequirementId
    # What was checked: the Requirement's screening text, and the corpus as it then stood.
    subject_fingerprint: str
    corpus_version: int
    embedding_identity: str
    provenance: Provenance
    matches: tuple[PriorArtMatch, ...]

    def __post_init__(self) -> None:
        if len(self.matches) > MATCHES_MAX:
            raise InvalidKnowledgeError(f"A prior-art check keeps at most {MATCHES_MAX} matches.")
        ids = [match.historic_requirement_id for match in self.matches]
        if len(set(ids)) != len(ids):
            raise InvalidKnowledgeError("A historic requirement is matched at most once.")

    @property
    def checked_at(self) -> datetime:
        return self.provenance.generated_at

    def key(self) -> str:
        """What a newer check must differ in to be worth making."""
        return f"{self.subject_fingerprint}:{self.corpus_version}"
