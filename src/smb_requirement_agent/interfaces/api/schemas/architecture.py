"""HTTP schemas for architecture impact mapping."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from smb_requirement_agent.breakdown.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobKind,
    ArchitectureJobStatus,
)
from smb_requirement_agent.breakdown.domain.architecture.entities import ArchitectureImpact
from smb_requirement_agent.references.domain.architecture.catalogue import (
    ArchitectureDependency,
    JourneyNeighbour,
    JourneyStep,
    OrganisationReference,
    ProductContext,
    SystemReference,
)
from smb_requirement_agent.references.domain.architecture.knowledge import RelationshipKind


class SystemCapabilityResponse(BaseModel):
    id: str
    name: str
    domain_id: str | None = None
    domain_path: list[str] = Field(
        default_factory=list, description="The capability's domain, from the top of the tree."
    )
    component_id: str | None = None
    component_name: str | None = Field(
        default=None, description="The system component that delivers it, when placed."
    )


class DomainSuggestionResponse(BaseModel):
    domain_id: str
    path: list[str]
    system_ids: list[str]
    matched_terms: list[str]
    system_names: list[str] = Field(default_factory=list)


class OfferingDutyResponse(BaseModel):
    component_id: str
    component_name: str
    system_id: str
    system_name: str
    role: str
    description: str


class ProductContextResponse(BaseModel):
    product_id: str
    product_name: str
    matched_terms: list[str]
    order_type: str | None = Field(default=None, description="The order type the item names.")
    responsibilities: list[OfferingDutyResponse] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, item: ProductContext) -> ProductContextResponse:
        return cls(
            product_id=item.product_id,
            product_name=item.product_name,
            matched_terms=list(item.matched_terms),
            order_type=item.order_type,
            responsibilities=[
                OfferingDutyResponse(
                    component_id=duty.component_id,
                    component_name=duty.component_name,
                    system_id=duty.system_id,
                    system_name=duty.system_name,
                    role=duty.role,
                    description=duty.description,
                )
                for duty in item.responsibilities
            ],
        )


class JourneyNeighbourResponse(BaseModel):
    number: str
    name: str
    system_id: str | None = None
    system_name: str | None = None

    @classmethod
    def from_domain(cls, item: JourneyNeighbour) -> JourneyNeighbourResponse:
        return cls(
            number=item.number,
            name=item.name,
            system_id=item.system_id,
            system_name=item.system_name,
        )


class JourneyStepResponse(BaseModel):
    system_id: str
    journey_id: str
    journey_name: str
    number: str
    name: str
    performs: bool = Field(description="True when the system performs it; false when it supports.")
    fulfils: list[str] = Field(
        default_factory=list, description="The offering and order type the journey fulfils."
    )
    before: list[JourneyNeighbourResponse] = Field(default_factory=list)
    after: list[JourneyNeighbourResponse] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, item: JourneyStep) -> JourneyStepResponse:
        return cls(
            system_id=item.system_id,
            journey_id=item.journey_id,
            journey_name=item.journey_name,
            number=item.number,
            name=item.name,
            performs=item.performs,
            fulfils=list(item.fulfils),
            before=[JourneyNeighbourResponse.from_domain(other) for other in item.before],
            after=[JourneyNeighbourResponse.from_domain(other) for other in item.after],
        )


class OrganisationReferenceResponse(BaseModel):
    id: str
    name: str


class SystemReferenceResponse(BaseModel):
    id: str
    name: str
    catalogued: bool
    capabilities: list[SystemCapabilityResponse]
    constraints: list[str]
    squads: list[OrganisationReferenceResponse]
    value_streams: list[OrganisationReferenceResponse]
    products: list[OrganisationReferenceResponse]


def _references(
    values: tuple[OrganisationReference, ...],
) -> list[OrganisationReferenceResponse]:
    return [OrganisationReferenceResponse(id=item.id, name=item.name) for item in values]


class ArchitectureDependencyResponse(BaseModel):
    source_system_id: str
    target_system_id: str
    description: str
    kind: RelationshipKind = RelationshipKind.UNSPECIFIED


def _system(system: SystemReference) -> SystemReferenceResponse:
    return SystemReferenceResponse(
        id=system.id,
        name=system.name,
        catalogued=system.catalogued,
        capabilities=[
            SystemCapabilityResponse(
                id=item.id,
                name=item.name,
                domain_id=item.domain_id,
                domain_path=list(item.domain_path),
                component_id=item.component_id,
                component_name=item.component_name,
            )
            for item in system.capabilities
        ],
        constraints=list(system.constraints),
        squads=_references(system.squads),
        value_streams=_references(system.value_streams),
        products=_references(system.products),
    )


def _dependency(item: ArchitectureDependency) -> ArchitectureDependencyResponse:
    return ArchitectureDependencyResponse(
        source_system_id=item.source_system_id,
        target_system_id=item.target_system_id,
        description=item.description,
        kind=item.kind,
    )


class ArchitectureCitationResponse(BaseModel):
    system_id: str
    chunk_id: str
    quote: str


class ArchitectureImpactResponse(BaseModel):
    knowledge_version: str
    mapped_at: datetime
    cross_system: bool
    systems: list[SystemReferenceResponse]
    dependencies: list[ArchitectureDependencyResponse]
    citation_ids: list[str]
    citations: list[ArchitectureCitationResponse] = Field(default_factory=list)
    uncertainty: str | None
    model: str | None = None
    embedding_model: str | None = None
    prompt_version: str | None = None
    index_revision: int | None = None
    evidence_classification: str = "legacy_deterministic"
    adjacent_systems: list[SystemReferenceResponse] = Field(
        default_factory=list,
        description="Systems one catalogued relationship away, listed to check, not mapped.",
    )
    adjacent_dependencies: list[ArchitectureDependencyResponse] = Field(default_factory=list)
    adjacent_omitted: int = 0
    suggested_domains: list[DomainSuggestionResponse] = Field(
        default_factory=list,
        description="Capability domains the wording matched when no catalogued system was found.",
    )
    product_contexts: list[ProductContextResponse] = Field(
        default_factory=list,
        description="Product offerings the item names, and the systems responsible: advice.",
    )
    journey_steps: list[JourneyStepResponse] = Field(
        default_factory=list,
        description="Journey activities the mapped systems perform or support: advice.",
    )
    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_domain(cls, impact: ArchitectureImpact) -> ArchitectureImpactResponse:
        return cls(
            knowledge_version=impact.knowledge_version,
            citation_ids=list(impact.citation_ids),
            citations=[
                ArchitectureCitationResponse(
                    system_id=item.system_id, chunk_id=item.chunk_id, quote=item.quote
                )
                for item in impact.citations
            ],
            uncertainty=impact.uncertainty,
            model=impact.model,
            embedding_model=impact.embedding_model,
            prompt_version=impact.prompt_version,
            index_revision=impact.index_revision,
            evidence_classification=impact.evidence_classification,
            mapped_at=impact.mapped_at,
            cross_system=impact.cross_system,
            systems=[_system(system) for system in impact.systems],
            dependencies=[_dependency(item) for item in impact.dependencies],
            adjacent_systems=[_system(system) for system in impact.adjacent_systems],
            adjacent_dependencies=[_dependency(item) for item in impact.adjacent_dependencies],
            adjacent_omitted=impact.adjacent_omitted,
            suggested_domains=[
                DomainSuggestionResponse(
                    domain_id=item.domain_id,
                    path=list(item.path),
                    system_ids=list(item.system_ids),
                    matched_terms=list(item.matched_terms),
                    system_names=list(item.system_names),
                )
                for item in impact.suggested_domains
            ],
            product_contexts=[
                ProductContextResponse.from_domain(item) for item in impact.product_contexts
            ],
            journey_steps=[JourneyStepResponse.from_domain(item) for item in impact.journey_steps],
        )


class ArchitectureJobResponse(BaseModel):
    """A queued mapping of a Requirement's backlog to the catalogue (ADR-0099)."""

    id: str
    kind: ArchitectureJobKind
    subject_id: str
    fingerprint: str
    actor_id: str
    status: ArchitectureJobStatus
    attempts: int = 0
    error_category: str | None = None
    lease_until: datetime | None = None

    @classmethod
    def from_domain(cls, job: ArchitectureJob) -> ArchitectureJobResponse:
        return cls(
            id=job.id,
            kind=job.kind,
            subject_id=job.subject_id,
            fingerprint=job.fingerprint,
            actor_id=job.actor_id,
            status=job.status,
            attempts=job.attempts,
            error_category=job.error_category,
            lease_until=job.lease_until,
        )
