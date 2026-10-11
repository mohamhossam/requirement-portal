"""Port for the knowledge service's whole-requirement assessment (ontology plan Phase 4).

The values mirror `POST /internal/architecture/assess` in the pinned
`contracts/knowledge-internal.openapi.json`, field for field. A system's role, a
path step's kind and a facet's kind are kept as text: the knowledge service may add
values to those lists (additive contract changes, AGENTS.md section 2.1), and an
unknown one is shown as written rather than failing the analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

VerdictValue = Literal[
    "change_existing_offering",
    "new_plan",
    "new_offering_in_family",
    "new_product_line",
]


@dataclass(frozen=True)
class AssessmentQuery:
    """A requirement as requirement work holds it: its text and its analysed facts."""

    text: tuple[str, ...]
    declared_systems: tuple[str, ...] = ()
    release_id: str | None = None
    # The requirement's own decided verdict is never shown back to it (ontology plan
    # Phase 5).
    requirement_id: str | None = None


@dataclass(frozen=True)
class AssessedConcept:
    concept_id: str
    label: str
    path: str
    weak: bool = False


@dataclass(frozen=True)
class AssessedFacet:
    kind: str
    text: str
    quote: str
    ref_id: str | None = None
    concepts: tuple[AssessedConcept, ...] = ()


@dataclass(frozen=True)
class AssessedCoverage:
    concept_id: str
    label: str
    path: str
    composed_by: tuple[str, ...]
    realised_by: tuple[str, ...]
    covered: bool


@dataclass(frozen=True)
class AssessedComponent:
    offering_id: str
    component_id: str
    name: str


@dataclass(frozen=True)
class DraftedResponsibility:
    system_id: str


@dataclass(frozen=True)
class DraftedComponent:
    id: str
    name: str
    responsibilities: tuple[DraftedResponsibility, ...] = ()


@dataclass(frozen=True)
class DraftedQuestion:
    id: str
    text: str


@dataclass(frozen=True)
class DraftedOffering:
    id: str
    name: str
    components: tuple[DraftedComponent, ...] = ()
    questions: tuple[DraftedQuestion, ...] = ()


@dataclass(frozen=True)
class DraftedActivity:
    number: str
    name: str


@dataclass(frozen=True)
class DraftedJourney:
    id: str
    name: str
    activities: tuple[DraftedActivity, ...] = ()


@dataclass(frozen=True)
class AssessedDraft:
    """The offering and journey drafted for a new-offering verdict (ontology plan Phase 9).

    Only what this application shows is read; `document` is the draft as the knowledge
    service wrote it, in the catalogue's own shapes, sent back unchanged with the approved
    backlog.
    """

    offering: DraftedOffering
    journey: DraftedJourney | None = None
    based_on: str | None = None
    document: dict[str, Any] = field(default_factory=dict, hash=False)


@dataclass(frozen=True)
class AssessedProposal:
    summary: str
    offering_id: str | None = None
    portfolio_node_id: str | None = None
    components: tuple[AssessedComponent, ...] = ()
    journey_ids: tuple[str, ...] = ()
    new_values: tuple[str, ...] = ()
    # Added in knowledge-portal 0.6.0, for a new offering in a family or a new product line.
    draft: AssessedDraft | None = None


@dataclass(frozen=True)
class AssessedPathStep:
    kind: str
    id: str
    label: str


@dataclass(frozen=True)
class AssessedSystem:
    id: str
    name: str
    role: str
    change_type: str
    paths: tuple[tuple[AssessedPathStep, ...], ...] = ()


@dataclass(frozen=True)
class AssessedGap:
    kind: str
    concept_id: str
    label: str
    reason: str
    system_id: str | None = None


@dataclass(frozen=True)
class AssessedOption:
    label: str
    id: str | None = None


@dataclass(frozen=True)
class AssessedQuestion:
    facet: str
    question: str
    options: tuple[AssessedOption, ...]


@dataclass(frozen=True)
class AssessedReference:
    id: str
    name: str


@dataclass(frozen=True)
class AssessedSeat:
    squad_id: str
    role: str
    person_id: str | None = None
    person_name: str | None = None
    scoped: bool = False


@dataclass(frozen=True)
class AssessedOwners:
    concept_id: str
    system_id: str
    squads: tuple[AssessedReference, ...] = ()
    value_streams: tuple[AssessedReference, ...] = ()
    seats: tuple[AssessedSeat, ...] = ()


@dataclass(frozen=True)
class ArchitectureAssessment:
    knowledge_version: str
    facets: tuple[AssessedFacet, ...]
    coverage: tuple[AssessedCoverage, ...]
    offering_id: str | None
    verdict: VerdictValue | None
    rule_verdict: VerdictValue | None
    verdict_reason: str
    proposal: AssessedProposal | None
    systems: tuple[AssessedSystem, ...]
    gaps: tuple[AssessedGap, ...] = ()
    questions: tuple[AssessedQuestion, ...] = ()
    owners: tuple[AssessedOwners, ...] = ()
    uncertainty: str | None = None
    model: str | None = None
    reader_model: str | None = None
    prompt_version: str | None = None


class ArchitectureAssessmentPort(Protocol):
    def is_connected(self) -> bool:
        """Whether a knowledge service is linked at all (ADR-0104)."""
        ...

    def assess(self, query: AssessmentQuery) -> ArchitectureAssessment | None:
        """The assessment, or None when the linked service does not offer one yet.

        Raises `ServiceUnavailableError` when the service cannot answer.
        """
        ...
