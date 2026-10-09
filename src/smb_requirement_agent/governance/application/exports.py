"""Provider-neutral, versioned backlog export contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

EXPORT_SCHEMA_VERSION = "1.5"


class ExportFormat(StrEnum):
    JSON = "json"
    XLSX = "xlsx"


@dataclass(frozen=True)
class ExportActor:
    id: str
    display_name: str
    email: str | None


@dataclass(frozen=True)
class ExportApproval:
    id: str
    subject_fingerprint: str
    recorded_by: ExportActor
    recorded_at: datetime
    rationale: str | None


@dataclass(frozen=True)
class ExportCounts:
    epics: int
    features: int
    stories: int
    acceptance_criteria: int


@dataclass(frozen=True)
class ExportManifest:
    requirement_id: str
    breakdown_revision: int
    revision_created_at: datetime
    final_approval: ExportApproval
    counts: ExportCounts


@dataclass(frozen=True)
class ExportProvenance:
    generated_at: datetime
    model: str
    prompt_version: str


@dataclass(frozen=True)
class ExportCapability:
    id: str
    name: str
    # Added in 1.3: the capability's domain, from the top of the tree down.
    domain_path: tuple[str, ...] = ()
    # Added in 1.4: the name of the system component that delivers it, if placed.
    component: str | None = None


@dataclass(frozen=True)
class ExportOrganisationReference:
    id: str
    name: str


@dataclass(frozen=True)
class ExportSystem:
    id: str
    name: str
    catalogued: bool
    capabilities: tuple[ExportCapability, ...]
    squads: tuple[ExportOrganisationReference, ...]
    value_streams: tuple[ExportOrganisationReference, ...]
    products: tuple[ExportOrganisationReference, ...]


@dataclass(frozen=True)
class ExportArchitectureDependency:
    source_system_id: str
    target_system_id: str
    description: str
    # Added in 1.2: how the source depends on the target, or "unspecified".
    kind: str = "unspecified"


@dataclass(frozen=True)
class ExportOfferingDuty:
    component_id: str
    component_name: str
    system_id: str
    system_name: str
    role: str
    description: str


@dataclass(frozen=True)
class ExportProductContext:
    """Added in 1.5: a product offering the item names, and who delivers it. Advice."""

    product_id: str
    product_name: str
    matched_terms: tuple[str, ...]
    order_type: str | None
    responsibilities: tuple[ExportOfferingDuty, ...]


@dataclass(frozen=True)
class ExportJourneyNeighbour:
    number: str
    name: str
    system_id: str | None
    system_name: str | None


@dataclass(frozen=True)
class ExportJourneyStep:
    """Added in 1.5: a journey activity a mapped system performs or supports. Advice."""

    system_id: str
    journey_id: str
    journey_name: str
    fulfils: tuple[str, ...]
    number: str
    name: str
    performs: bool
    before: tuple[ExportJourneyNeighbour, ...]
    after: tuple[ExportJourneyNeighbour, ...]


@dataclass(frozen=True)
class ExportArchitecture:
    knowledge_version: str
    mapped_at: datetime
    systems: tuple[ExportSystem, ...]
    dependencies: tuple[ExportArchitectureDependency, ...]
    # Added in 1.1: systems one catalogued relationship away, listed to check, not mapped.
    adjacent_systems: tuple[ExportSystem, ...] = ()
    adjacent_dependencies: tuple[ExportArchitectureDependency, ...] = ()
    # Added in 1.5: product offerings the item names and the journey steps of its mapped
    # systems, for a reviewer to check, not mapped (ADR-0097).
    product_contexts: tuple[ExportProductContext, ...] = ()
    journey_steps: tuple[ExportJourneyStep, ...] = ()


@dataclass(frozen=True)
class ExportAcceptanceCriterion:
    sequence: int
    given: str
    when: str
    then: str


@dataclass(frozen=True)
class ExportStory:
    sequence: int
    id: str
    feature_id: str
    role: str
    action: str
    value: str
    voice: str
    status: str
    provenance: ExportProvenance
    acceptance_criteria: tuple[ExportAcceptanceCriterion, ...]
    architecture: ExportArchitecture | None


@dataclass(frozen=True)
class ExportFeature:
    sequence: int
    id: str
    epic_id: str
    name: str
    outcome: str
    delivery_drop: str
    splitting_pattern: str
    splitting_rationale: str
    status: str
    provenance: ExportProvenance
    architecture: ExportArchitecture | None
    stories: tuple[ExportStory, ...]


@dataclass(frozen=True)
class ExportEpic:
    id: str
    requirement_id: str
    name: str
    outcome: str
    business_case: str
    status: str
    provenance: ExportProvenance
    features: tuple[ExportFeature, ...]


@dataclass(frozen=True)
class NeutralBacklogExport:
    schema_version: str
    manifest: ExportManifest
    epic: ExportEpic


@dataclass(frozen=True)
class ExportArtifact:
    filename: str
    media_type: str
    content: bytes
