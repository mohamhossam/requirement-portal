"""The Business Requirements Document rendered from a confirmed analysis (ADR-0119).

A versioned, provider-neutral contract of its own. It is not the neutral backlog export
(ADR-0023), which knowledge-portal reads and which deliberately excludes the analysis. Every
value here is copied from an immutable revision; nothing is generated. Uncertainty stays
visible: assumptions, dependencies, open questions and ambiguities carry their own status, and
the backlog appears only once it holds a formal final approval.

People appear by display name only. The document leaves the system, so it carries no email
addresses and no actor ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

SPECIFICATION_SCHEMA_VERSION = "1.2"
SPECIFICATION_GENERATOR = "SMB AI Requirement Breakdown Agent"
SPECIFICATION_TITLE = "Business Requirements Document"


class SpecificationFormat(StrEnum):
    DOCX = "docx"
    MARKDOWN = "md"


class StatementOrigin(StrEnum):
    """Where a requirement statement came from."""

    CAPTURED = "captured"
    ANALYSIS = "analysis"
    ACCEPTED_PROPOSAL = "accepted_proposal"


class SpecificationVersionKind(StrEnum):
    """Which immutable history a version entry comes from (ADR-0009)."""

    REQUIREMENT = "requirement"
    BREAKDOWN = "breakdown"


@dataclass(frozen=True)
class SpecificationActor:
    display_name: str


@dataclass(frozen=True)
class SpecificationSignature:
    """A person's recorded act: a confirmation, an approval or a decision."""

    actor: SpecificationActor
    recorded_at: datetime
    rationale: str | None = None


@dataclass(frozen=True)
class SpecificationVersion:
    """One row of the version history: a revision and what changed in it. Added in 1.1."""

    kind: SpecificationVersionKind
    number: int
    recorded_at: datetime
    summary: str


@dataclass(frozen=True)
class SpecificationManifest:
    requirement_id: str
    title: str
    requirement_version: int
    breakdown_revision: int
    revision_created_at: datetime
    analysis_round: int | None
    analysis_generated_at: datetime | None
    analysis_model: str | None
    analysis_prompt_version: str | None
    confirmation: SpecificationSignature
    backlog_approval: SpecificationSignature | None
    generator: str = SPECIFICATION_GENERATOR


@dataclass(frozen=True)
class SpecificationCounts:
    business_requirements: int
    business_rules: int
    constraints: int
    assumptions: int
    dependencies: int
    open_questions: int
    ambiguities: int
    resolved_clarifications: int


@dataclass(frozen=True)
class SpecificationSummary:
    description: str
    counts: SpecificationCounts


@dataclass(frozen=True)
class SpecificationObjectives:
    desired_outcome: str | None
    origin: StatementOrigin | None
    success_measures: tuple[str, ...]


@dataclass(frozen=True)
class SpecificationScope:
    customer_context: str | None
    channels: tuple[str, ...]
    systems: tuple[str, ...]
    # Added in 1.2: the scope statement a standard BRD carries.
    out_of_scope: tuple[str, ...] = ()
    current_state: str | None = None
    proposed_state: str | None = None


@dataclass(frozen=True)
class SpecificationStakeholder:
    display_name: str
    role: str
    since: datetime


@dataclass(frozen=True)
class SpecificationEvidence:
    filename: str
    label: str


@dataclass(frozen=True)
class SpecificationStatement:
    id: str
    text: str
    origin: StatementOrigin
    evidence: tuple[SpecificationEvidence, ...] = ()


@dataclass(frozen=True)
class SpecificationResolution:
    answer: str
    answered_by: SpecificationActor | None
    answered_at: datetime | None


@dataclass(frozen=True)
class SpecificationResolvable:
    """An uncertainty the analysis raised, open or resolved by a person."""

    id: str
    text: str
    rationale: str | None
    evidence: tuple[SpecificationEvidence, ...]
    resolution: SpecificationResolution | None


@dataclass(frozen=True)
class SpecificationImpactSystem:
    name: str
    role: str
    change_type: str


@dataclass(frozen=True)
class SpecificationImpactGap:
    label: str
    reason: str


@dataclass(frozen=True)
class SpecificationProductImpact:
    status: str
    suggested_verdict: str | None
    verdict: str | None
    decision: str | None
    reason: str
    offering_name: str | None
    systems: tuple[SpecificationImpactSystem, ...]
    gaps: tuple[SpecificationImpactGap, ...]
    decided: SpecificationSignature | None


@dataclass(frozen=True)
class SpecificationCriterion:
    given: str
    when: str
    then: str


@dataclass(frozen=True)
class SpecificationStory:
    id: str
    role: str
    action: str
    value: str
    kind: str
    criteria: tuple[SpecificationCriterion, ...]


@dataclass(frozen=True)
class SpecificationFeature:
    id: str
    name: str
    outcome: str
    delivery_drop: str
    kind: str
    acceptance_criteria: tuple[str, ...]
    stories: tuple[SpecificationStory, ...]


@dataclass(frozen=True)
class SpecificationEpic:
    name: str
    outcome: str
    business_case: str


@dataclass(frozen=True)
class SpecificationRisk:
    severity: str
    description: str


@dataclass(frozen=True)
class SpecificationBacklog:
    """The approved backlog, as functional requirements. Present only once formally approved."""

    epic: SpecificationEpic
    features: tuple[SpecificationFeature, ...]
    approval: SpecificationSignature
    dependencies: tuple[str, ...]
    risks: tuple[SpecificationRisk, ...]


@dataclass(frozen=True)
class SpecificationSourceDocument:
    filename: str
    version_id: str
    checksum_sha256: str


@dataclass(frozen=True)
class SpecificationGlossaryEntry:
    term: str
    definition: str


GLOSSARY: tuple[SpecificationGlossaryEntry, ...] = (
    SpecificationGlossaryEntry(
        "Business requirement (BR)",
        "A fact about the business need the analysis found in the source and the owner confirmed.",
    ),
    SpecificationGlossaryEntry(
        "Business rule (RL)",
        "A policy or decision rule the solution must follow, captured with the need, found by "
        "the analysis or accepted as a proposal.",
    ),
    SpecificationGlossaryEntry(
        "Constraint (CN)", "A limit on how the need may be met: time, budget, technology or policy."
    ),
    SpecificationGlossaryEntry(
        "Assumption (AS)",
        "Something taken to be true without evidence in the source. It is not a confirmed "
        "requirement until a person resolves it.",
    ),
    SpecificationGlossaryEntry(
        "Dependency (DP)", "Something outside this requirement that its delivery relies on."
    ),
    SpecificationGlossaryEntry(
        "Open question (OQ)", "Information the source does not give and a person must supply."
    ),
    SpecificationGlossaryEntry(
        "Ambiguity (AM)", "Wording in the source that allows more than one reading."
    ),
    SpecificationGlossaryEntry(
        "Functional requirement (FR)",
        "A Feature of the approved backlog, with its User Stories and acceptance criteria.",
    ),
    SpecificationGlossaryEntry(
        "Evidence",
        "The source document and passage a statement was taken from, by file name and label.",
    ),
)


@dataclass(frozen=True)
class RequirementSpecification:
    schema_version: str
    manifest: SpecificationManifest
    summary: SpecificationSummary
    objectives: SpecificationObjectives
    scope: SpecificationScope
    stakeholders: tuple[SpecificationStakeholder, ...]
    business_requirements: tuple[SpecificationStatement, ...]
    business_rules: tuple[SpecificationStatement, ...]
    constraints: tuple[SpecificationStatement, ...]
    assumptions: tuple[SpecificationResolvable, ...]
    dependencies: tuple[SpecificationResolvable, ...]
    open_questions: tuple[SpecificationResolvable, ...]
    ambiguities: tuple[SpecificationResolvable, ...]
    product_impact: SpecificationProductImpact | None
    functional_requirements: SpecificationBacklog | None
    source_documents: tuple[SpecificationSourceDocument, ...]
    # Added in 1.1: every revision up to this one, in time order.
    versions: tuple[SpecificationVersion, ...]
    glossary: tuple[SpecificationGlossaryEntry, ...] = GLOSSARY
