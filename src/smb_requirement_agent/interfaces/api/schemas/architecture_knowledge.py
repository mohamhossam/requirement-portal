"""HTTP schemas for architecture knowledge administration and architecture jobs.

The API owns these shapes so the knowledge domain can evolve without silently
changing the browser contract. Field names and JSON values match the releases
the API returned when it serialised the domain dataclasses directly.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from smb_requirement_agent.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobKind,
    ArchitectureJobStatus,
)
from smb_requirement_agent.application.ports.catalogue_candidates import ExtractionRun
from smb_requirement_agent.application.ports.located_document_extractor import LocatedText
from smb_requirement_agent.application.use_cases.architecture_comparison import (
    ComparedImpact,
    ImpactComparison,
)
from smb_requirement_agent.application.use_cases.architecture_documents import DocumentPassage
from smb_requirement_agent.application.use_cases.architecture_mapping_impact import MappingImpact
from smb_requirement_agent.application.use_cases.catalogue_candidates import (
    CandidateOverview,
    CandidateView,
)
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateBasis,
    CandidateContent,
    CandidateKind,
    CandidateMatch,
    CandidateStatus,
    MatchRole,
    PossibleMatch,
)
from smb_requirement_agent.domain.architecture.diff import (
    CatalogueDiff,
    ChangedItem,
    ChangeKind,
)
from smb_requirement_agent.domain.architecture.journeys import (
    Activity,
    ActivityIntegration,
    FlowRule,
    FlowRuleKind,
    Journey,
    journey_edges,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    CapabilityDomain,
    KnowledgeAuditEvent,
    KnowledgeCapability,
    KnowledgeDocumentVersion,
    KnowledgeReleaseStatus,
    LandscapeDomain,
    RelationshipKind,
    SystemComponent,
    SystemDefinition,
    SystemRelationship,
)
from smb_requirement_agent.domain.architecture.products import (
    ComponentResponsibility,
    OfferingComponent,
    OfferingPoint,
    OrderType,
    ProductOffering,
    SourceConfidence,
)
from smb_requirement_agent.domain.architecture.samples import MAX_SAMPLES, SampleRequirementSet
from smb_requirement_agent.interfaces.api.schemas.bounds import (
    MAX_CATALOGUE_ITEMS,
    Identifier,
    Name,
    Sentence,
    Text,
)

# The catalogue schemas below are also response shapes. Their size limits apply
# to requests; `from_domain` builds them with `model_construct`, skipping
# validation, so a stored release always reads back.


class KnowledgeCapabilitySchema(BaseModel):
    id: Identifier
    name: Name
    triggers: list[Sentence] = Field(max_length=MAX_CATALOGUE_ITEMS)
    domain_id: Identifier | None = None
    component_id: Identifier | None = None

    @classmethod
    def from_domain(cls, capability: KnowledgeCapability) -> KnowledgeCapabilitySchema:
        return cls.model_construct(
            id=capability.id,
            name=capability.name,
            triggers=list(capability.triggers),
            domain_id=capability.domain_id,
            component_id=capability.component_id,
        )

    def to_domain(self) -> KnowledgeCapability:
        return KnowledgeCapability(
            self.id, self.name, tuple(self.triggers), self.domain_id, self.component_id
        )


class SystemComponentSchema(BaseModel):
    id: Identifier
    name: Name
    name_ar: Name | None = None
    description: Text | None = None
    aliases: list[Name] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    technology: Name | None = None

    @classmethod
    def from_domain(cls, component: SystemComponent) -> SystemComponentSchema:
        return cls.model_construct(
            id=component.id,
            name=component.name,
            name_ar=component.name_ar,
            description=component.description,
            aliases=list(component.aliases),
            technology=component.technology,
        )

    def to_domain(self) -> SystemComponent:
        return SystemComponent(
            self.id,
            self.name,
            self.name_ar,
            self.description,
            tuple(self.aliases),
            self.technology,
        )


class CapabilityDomainSchema(BaseModel):
    id: Identifier
    name: Name
    name_ar: Name | None = None
    parent_id: Identifier | None = None
    description: Text | None = None

    @classmethod
    def from_domain(cls, domain: CapabilityDomain) -> CapabilityDomainSchema:
        return cls.model_construct(
            id=domain.id,
            name=domain.name,
            name_ar=domain.name_ar,
            parent_id=domain.parent_id,
            description=domain.description,
        )

    def to_domain(self) -> CapabilityDomain:
        return CapabilityDomain(self.id, self.name, self.name_ar, self.parent_id, self.description)


class LandscapeDomainSchema(BaseModel):
    """Where systems sit in the landscape; a sub-domain names its parent (ADR-0094)."""

    id: Identifier
    name: Name
    name_ar: Name | None = None
    parent_id: Identifier | None = None
    description: Text | None = None

    @classmethod
    def from_domain(cls, domain: LandscapeDomain) -> LandscapeDomainSchema:
        return cls.model_construct(
            id=domain.id,
            name=domain.name,
            name_ar=domain.name_ar,
            parent_id=domain.parent_id,
            description=domain.description,
        )

    def to_domain(self) -> LandscapeDomain:
        return LandscapeDomain(self.id, self.name, self.name_ar, self.parent_id, self.description)


class OfferingPointSchema(BaseModel):
    """A customer value, or a kind of customer an offering is for."""

    name: Name
    description: Text | None = None
    confidence: SourceConfidence | None = None
    source: Text | None = None

    @classmethod
    def from_domain(cls, point: OfferingPoint) -> OfferingPointSchema:
        return cls.model_construct(
            name=point.name,
            description=point.description,
            confidence=point.confidence,
            source=point.source,
        )

    def to_domain(self) -> OfferingPoint:
        return OfferingPoint(self.name, self.description, self.confidence, self.source)


class OrderTypeSchema(BaseModel):
    code: Identifier
    name: Name
    enabled: bool = True
    description: Text | None = None
    confidence: SourceConfidence | None = None
    source: Text | None = None

    @classmethod
    def from_domain(cls, order: OrderType) -> OrderTypeSchema:
        return cls.model_construct(
            code=order.code,
            name=order.name,
            enabled=order.enabled,
            description=order.description,
            confidence=order.confidence,
            source=order.source,
        )

    def to_domain(self) -> OrderType:
        return OrderType(
            self.code, self.name, self.enabled, self.description, self.confidence, self.source
        )


class ComponentResponsibilitySchema(BaseModel):
    system_id: Identifier
    role: Name
    description: Text
    order_types: list[Identifier] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    confidence: SourceConfidence | None = None
    source: Text | None = None

    @classmethod
    def from_domain(cls, item: ComponentResponsibility) -> ComponentResponsibilitySchema:
        return cls.model_construct(
            system_id=item.system_id,
            role=item.role,
            description=item.description,
            order_types=list(item.order_types),
            confidence=item.confidence,
            source=item.source,
        )

    def to_domain(self) -> ComponentResponsibility:
        return ComponentResponsibility(
            self.system_id,
            self.role,
            self.description,
            tuple(self.order_types),
            self.confidence,
            self.source,
        )


class OfferingComponentSchema(BaseModel):
    id: Identifier
    name: Name
    code: Name | None = None
    kind: Name | None = None
    mandatory: bool | None = None
    customer_visible: bool | None = None
    description: Text | None = None
    commercial_spec: Text | None = None
    technical_spec: Text | None = None
    technical_details: Text | None = None
    responsibilities: list[ComponentResponsibilitySchema] = Field(
        default=[], max_length=MAX_CATALOGUE_ITEMS
    )
    confidence: SourceConfidence | None = None
    source: Text | None = None

    @classmethod
    def from_domain(cls, component: OfferingComponent) -> OfferingComponentSchema:
        return cls.model_construct(
            id=component.id,
            name=component.name,
            code=component.code,
            kind=component.kind,
            mandatory=component.mandatory,
            customer_visible=component.customer_visible,
            description=component.description,
            commercial_spec=component.commercial_spec,
            technical_spec=component.technical_spec,
            technical_details=component.technical_details,
            responsibilities=[
                ComponentResponsibilitySchema.from_domain(item)
                for item in component.responsibilities
            ],
            confidence=component.confidence,
            source=component.source,
        )

    def to_domain(self) -> OfferingComponent:
        return OfferingComponent(
            id=self.id,
            name=self.name,
            code=self.code,
            kind=self.kind,
            mandatory=self.mandatory,
            customer_visible=self.customer_visible,
            description=self.description,
            commercial_spec=self.commercial_spec,
            technical_spec=self.technical_spec,
            technical_details=self.technical_details,
            responsibilities=tuple(item.to_domain() for item in self.responsibilities),
            confidence=self.confidence,
            source=self.source,
        )


class ProductOfferingSchema(BaseModel):
    """A commercial offering, its order types and components, and the systems behind them."""

    id: Identifier
    name: Name
    code: Name | None = None
    family: Name | None = None
    version: Name | None = None
    lifecycle: Name | None = None
    proposition: Text | None = None
    rules: list[Text] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    order_types: list[OrderTypeSchema] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    components: list[OfferingComponentSchema] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    values: list[OfferingPointSchema] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    audiences: list[OfferingPointSchema] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    confidence: SourceConfidence | None = None
    source: Text | None = None

    @classmethod
    def from_domain(cls, offering: ProductOffering) -> ProductOfferingSchema:
        return cls.model_construct(
            id=offering.id,
            name=offering.name,
            code=offering.code,
            family=offering.family,
            version=offering.version,
            lifecycle=offering.lifecycle,
            proposition=offering.proposition,
            rules=list(offering.rules),
            order_types=[OrderTypeSchema.from_domain(item) for item in offering.order_types],
            components=[OfferingComponentSchema.from_domain(item) for item in offering.components],
            values=[OfferingPointSchema.from_domain(item) for item in offering.values],
            audiences=[OfferingPointSchema.from_domain(item) for item in offering.audiences],
            confidence=offering.confidence,
            source=offering.source,
        )

    def to_domain(self) -> ProductOffering:
        return ProductOffering(
            id=self.id,
            name=self.name,
            code=self.code,
            family=self.family,
            version=self.version,
            lifecycle=self.lifecycle,
            proposition=self.proposition,
            rules=tuple(self.rules),
            order_types=tuple(item.to_domain() for item in self.order_types),
            components=tuple(item.to_domain() for item in self.components),
            values=tuple(item.to_domain() for item in self.values),
            audiences=tuple(item.to_domain() for item in self.audiences),
            confidence=self.confidence,
            source=self.source,
        )


class ActivitySchema(BaseModel):
    number: Identifier
    name: Name
    phase: Name | None = None
    track: Name | None = None
    performing_system_id: Identifier | None = None
    supporting_system_ids: list[Identifier] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    system_function: Text | None = None
    mode: Name | None = None
    customer_visible: bool | None = None
    description: Text | None = None
    component_ids: list[Identifier] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    input: Text | None = None
    output: Text | None = None
    etom: Text | None = None
    confidence: SourceConfidence | None = None
    source: Text | None = None

    @classmethod
    def from_domain(cls, item: Activity) -> ActivitySchema:
        return cls.model_construct(
            number=item.number,
            name=item.name,
            phase=item.phase,
            track=item.track,
            performing_system_id=item.performing_system_id,
            supporting_system_ids=list(item.supporting_system_ids),
            system_function=item.system_function,
            mode=item.mode,
            customer_visible=item.customer_visible,
            description=item.description,
            component_ids=list(item.component_ids),
            input=item.input,
            output=item.output,
            etom=item.etom,
            confidence=item.confidence,
            source=item.source,
        )

    def to_domain(self) -> Activity:
        return Activity(
            number=self.number,
            name=self.name,
            phase=self.phase,
            track=self.track,
            performing_system_id=self.performing_system_id,
            supporting_system_ids=tuple(self.supporting_system_ids),
            system_function=self.system_function,
            mode=self.mode,
            customer_visible=self.customer_visible,
            description=self.description,
            component_ids=tuple(self.component_ids),
            input=self.input,
            output=self.output,
            etom=self.etom,
            confidence=self.confidence,
            source=self.source,
        )


class FlowRuleSchema(BaseModel):
    kind: FlowRuleKind
    from_activity: Identifier
    to_activity: Identifier
    condition: Name | None = None
    branch: Name | None = None
    parallel_group: Name | None = None
    rejoin_at: Identifier | None = None
    confidence: SourceConfidence | None = None
    source: Text | None = None

    @classmethod
    def from_domain(cls, rule: FlowRule) -> FlowRuleSchema:
        return cls.model_construct(
            kind=rule.kind,
            from_activity=rule.from_activity,
            to_activity=rule.to_activity,
            condition=rule.condition,
            branch=rule.branch,
            parallel_group=rule.parallel_group,
            rejoin_at=rule.rejoin_at,
            confidence=rule.confidence,
            source=rule.source,
        )

    def to_domain(self) -> FlowRule:
        return FlowRule(
            self.kind,
            self.from_activity,
            self.to_activity,
            self.condition,
            self.branch,
            self.parallel_group,
            self.rejoin_at,
            self.confidence,
            self.source,
        )


class ActivityIntegrationSchema(BaseModel):
    from_activity: Identifier
    to_activity: Identifier
    interaction: Name | None = None
    interface: Text | None = None
    payload: Text | None = None
    timing: Name | None = None
    correlation_key: Name | None = None
    confidence: SourceConfidence | None = None
    source: Text | None = None

    @classmethod
    def from_domain(cls, link: ActivityIntegration) -> ActivityIntegrationSchema:
        return cls.model_construct(
            from_activity=link.from_activity,
            to_activity=link.to_activity,
            interaction=link.interaction,
            interface=link.interface,
            payload=link.payload,
            timing=link.timing,
            correlation_key=link.correlation_key,
            confidence=link.confidence,
            source=link.source,
        )

    def to_domain(self) -> ActivityIntegration:
        return ActivityIntegration(
            self.from_activity,
            self.to_activity,
            self.interaction,
            self.interface,
            self.payload,
            self.timing,
            self.correlation_key,
            self.confidence,
            self.source,
        )


class JourneyEdgeResponse(BaseModel):
    # Bounded like any request field, since a client may send a journey back with them.
    from_activity: Identifier
    to_activity: Identifier
    kind: Identifier
    label: Name | None = None


class JourneySchema(BaseModel):
    """A journey and, read-only, the flow derived from its order and rules (ADR-0096)."""

    id: Identifier
    name: Name
    product_id: Identifier | None = None
    order_type_code: Identifier | None = None
    description: Text | None = None
    activities: list[ActivitySchema] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    flow_rules: list[FlowRuleSchema] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    integrations: list[ActivityIntegrationSchema] = Field(
        default=[], max_length=MAX_CATALOGUE_ITEMS
    )
    confidence: SourceConfidence | None = None
    source: Text | None = None
    # Derived on the way out and ignored on the way in: the flow is never stored.
    edges: list[JourneyEdgeResponse] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS * 4)

    @classmethod
    def from_domain(cls, journey: Journey) -> JourneySchema:
        return cls.model_construct(
            id=journey.id,
            name=journey.name,
            product_id=journey.product_id,
            order_type_code=journey.order_type_code,
            description=journey.description,
            activities=[ActivitySchema.from_domain(item) for item in journey.activities],
            flow_rules=[FlowRuleSchema.from_domain(item) for item in journey.flow_rules],
            integrations=[
                ActivityIntegrationSchema.from_domain(item) for item in journey.integrations
            ],
            confidence=journey.confidence,
            source=journey.source,
            edges=[
                JourneyEdgeResponse.model_construct(
                    from_activity=edge.from_activity,
                    to_activity=edge.to_activity,
                    kind=edge.kind,
                    label=edge.label,
                )
                for edge in journey_edges(journey)
            ],
        )

    def to_domain(self) -> Journey:
        return Journey(
            id=self.id,
            name=self.name,
            product_id=self.product_id,
            order_type_code=self.order_type_code,
            description=self.description,
            activities=tuple(item.to_domain() for item in self.activities),
            flow_rules=tuple(item.to_domain() for item in self.flow_rules),
            integrations=tuple(item.to_domain() for item in self.integrations),
            confidence=self.confidence,
            source=self.source,
        )


class SystemDefinitionSchema(BaseModel):
    id: Identifier
    name: Name
    aliases: list[Name] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    capabilities: list[KnowledgeCapabilitySchema] = Field(
        default=[], max_length=MAX_CATALOGUE_ITEMS
    )
    constraints: list[Text] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    name_ar: Name | None = None
    components: list[SystemComponentSchema] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    description: Text | None = None
    landscape_domain_id: Identifier | None = None

    @classmethod
    def from_domain(cls, system: SystemDefinition) -> SystemDefinitionSchema:
        return cls.model_construct(
            id=system.id,
            name=system.name,
            aliases=list(system.aliases),
            capabilities=[KnowledgeCapabilitySchema.from_domain(c) for c in system.capabilities],
            constraints=list(system.constraints),
            name_ar=system.name_ar,
            components=[SystemComponentSchema.from_domain(c) for c in system.components],
            description=system.description,
            landscape_domain_id=system.landscape_domain_id,
        )

    def to_domain(self) -> SystemDefinition:
        return SystemDefinition(
            id=self.id,
            name=self.name,
            aliases=tuple(self.aliases),
            capabilities=tuple(item.to_domain() for item in self.capabilities),
            constraints=tuple(self.constraints),
            name_ar=self.name_ar,
            components=tuple(item.to_domain() for item in self.components),
            description=self.description,
            landscape_domain_id=self.landscape_domain_id,
        )


class SystemRelationshipSchema(BaseModel):
    source_system_id: Identifier
    target_system_id: Identifier
    description: Text
    kind: RelationshipKind = RelationshipKind.UNSPECIFIED

    @classmethod
    def from_domain(cls, relationship: SystemRelationship) -> SystemRelationshipSchema:
        return cls.model_construct(
            source_system_id=relationship.source_system_id,
            target_system_id=relationship.target_system_id,
            description=relationship.description,
            kind=relationship.kind,
        )

    def to_domain(self) -> SystemRelationship:
        return SystemRelationship(
            self.source_system_id, self.target_system_id, self.description, self.kind
        )


class KnowledgeDocumentVersionResponse(BaseModel):
    id: str
    title: str
    filename: str
    mime_type: str
    language: str
    checksum: str
    storage_key: str
    uploaded_by: str
    uploaded_at: datetime

    @classmethod
    def from_domain(cls, version: KnowledgeDocumentVersion) -> KnowledgeDocumentVersionResponse:
        return cls(
            id=version.id,
            title=version.title,
            filename=version.filename,
            mime_type=version.mime_type,
            language=version.language,
            checksum=version.checksum,
            storage_key=version.storage_key,
            uploaded_by=version.uploaded_by,
            uploaded_at=version.uploaded_at,
        )


class KnowledgeReleaseResponse(BaseModel):
    id: str
    revision: int
    systems: list[SystemDefinitionSchema] = Field(max_length=MAX_CATALOGUE_ITEMS)
    relationships: list[SystemRelationshipSchema] = Field(max_length=MAX_CATALOGUE_ITEMS)
    documents: list[KnowledgeDocumentVersionResponse] = []
    status: KnowledgeReleaseStatus = KnowledgeReleaseStatus.DRAFT
    built_revision: int | None = None
    published_at: datetime | None = None
    published_by: str | None = None
    index_profile: str | None = None
    index_hash: str | None = None
    index_id: str | None = None
    name: str | None = None
    created_by: str | None = None
    capability_domains: list[CapabilityDomainSchema] = Field(
        default_factory=list, max_length=MAX_CATALOGUE_ITEMS
    )
    landscape_domains: list[LandscapeDomainSchema] = Field(
        default_factory=list, max_length=MAX_CATALOGUE_ITEMS
    )
    products: list[ProductOfferingSchema] = Field(
        default_factory=list, max_length=MAX_CATALOGUE_ITEMS
    )
    journeys: list[JourneySchema] = Field(default_factory=list, max_length=MAX_CATALOGUE_ITEMS)

    @classmethod
    def from_domain(cls, release: ArchitectureKnowledge) -> KnowledgeReleaseResponse:
        return cls(
            id=release.id,
            revision=release.revision,
            systems=[SystemDefinitionSchema.from_domain(item) for item in release.systems],
            relationships=[
                SystemRelationshipSchema.from_domain(item) for item in release.relationships
            ],
            documents=[
                KnowledgeDocumentVersionResponse.from_domain(item) for item in release.documents
            ],
            status=release.status,
            built_revision=release.built_revision,
            published_at=release.published_at,
            published_by=release.published_by,
            index_profile=release.index_profile,
            index_hash=release.index_hash,
            index_id=release.index_id,
            name=release.name,
            created_by=release.created_by,
            capability_domains=[
                CapabilityDomainSchema.from_domain(item) for item in release.capability_domains
            ],
            landscape_domains=[
                LandscapeDomainSchema.from_domain(item) for item in release.landscape_domains
            ],
            products=[ProductOfferingSchema.from_domain(item) for item in release.products],
            journeys=[JourneySchema.from_domain(item) for item in release.journeys],
        )


class KnowledgeAuditEventResponse(BaseModel):
    release_id: str
    actor_id: str
    action: str
    revision: int
    rationale: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, event: KnowledgeAuditEvent) -> KnowledgeAuditEventResponse:
        return cls(
            release_id=event.release_id,
            actor_id=event.actor_id,
            action=event.action,
            revision=event.revision,
            rationale=event.rationale,
            created_at=event.created_at,
        )


class ArchitectureJobResponse(BaseModel):
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


class DraftUpdateRequest(BaseModel):
    expected_revision: int
    systems: list[SystemDefinitionSchema] = Field(max_length=MAX_CATALOGUE_ITEMS)
    relationships: list[SystemRelationshipSchema] = Field(max_length=MAX_CATALOGUE_ITEMS)
    # Omitted by clients that predate domains: the draft keeps the ones it has.
    capability_domains: list[CapabilityDomainSchema] | None = Field(
        default=None, max_length=MAX_CATALOGUE_ITEMS
    )
    # Likewise for clients that predate landscape domains (ADR-0094).
    landscape_domains: list[LandscapeDomainSchema] | None = Field(
        default=None, max_length=MAX_CATALOGUE_ITEMS
    )
    # Likewise for product offerings (ADR-0095).
    products: list[ProductOfferingSchema] | None = Field(
        default=None, max_length=MAX_CATALOGUE_ITEMS
    )
    # Likewise for journeys (ADR-0096).
    journeys: list[JourneySchema] | None = Field(default=None, max_length=MAX_CATALOGUE_ITEMS)


class SystemUpdateRequest(BaseModel):
    expected_revision: int
    system: SystemDefinitionSchema


class RevisionRequest(BaseModel):
    expected_revision: int


class CreateVersionRequest(BaseModel):
    name: Name


class RenameVersionRequest(RevisionRequest):
    name: Name


class PublishRequest(RevisionRequest):
    rationale: Text


class ActivateRequest(BaseModel):
    rationale: Text


class DocumentSelectionRequest(RevisionRequest):
    version_ids: list[Identifier] = Field(max_length=MAX_CATALOGUE_ITEMS)


class CatalogueChangeResponse(BaseModel):
    item: ChangedItem
    change: ChangeKind
    key: str
    label: str
    fields: list[str]


class CatalogueDiffResponse(BaseModel):
    base_release_id: str
    draft_release_id: str
    changes: list[CatalogueChangeResponse]

    @classmethod
    def from_domain(cls, diff: CatalogueDiff) -> CatalogueDiffResponse:
        return cls(
            base_release_id=diff.base_release_id,
            draft_release_id=diff.draft_release_id,
            changes=[
                CatalogueChangeResponse(
                    item=item.item,
                    change=item.change,
                    key=item.key,
                    label=item.label,
                    fields=list(item.fields),
                )
                for item in diff.changes
            ],
        )


class CandidateContentSchema(BaseModel):
    kind: CandidateKind
    system_id: Identifier
    name: Name = ""
    name_ar: Name | None = None
    aliases: list[Name] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    capability_id: Identifier | None = None
    triggers: list[Sentence] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    target_system_id: Identifier | None = None
    text: Text = ""
    relationship_kind: RelationshipKind | None = None
    component_id: Identifier | None = None
    description: Text | None = None
    technology: Name | None = None
    landscape_domain_id: Identifier | None = None
    parent_domain_id: Identifier | None = None
    # The whole offering, for a product suggestion (ADR-0095).
    product: ProductOfferingSchema | None = None
    # The whole journey, for a journey suggestion (ADR-0096).
    journey: JourneySchema | None = None

    @classmethod
    def from_domain(cls, content: CandidateContent) -> CandidateContentSchema:
        return cls.model_construct(
            kind=content.kind,
            system_id=content.system_id,
            name=content.name,
            name_ar=content.name_ar,
            aliases=list(content.aliases),
            capability_id=content.capability_id,
            triggers=list(content.triggers),
            target_system_id=content.target_system_id,
            text=content.text,
            relationship_kind=content.relationship_kind,
            component_id=content.component_id,
            description=content.description,
            technology=content.technology,
            landscape_domain_id=content.landscape_domain_id,
            parent_domain_id=content.parent_domain_id,
            product=(
                ProductOfferingSchema.from_domain(content.product) if content.product else None
            ),
            journey=JourneySchema.from_domain(content.journey) if content.journey else None,
        )

    def to_domain(self) -> CandidateContent:
        return CandidateContent(
            self.kind,
            self.system_id,
            self.name,
            self.name_ar,
            tuple(self.aliases),
            self.capability_id,
            tuple(self.triggers),
            self.target_system_id,
            self.text,
            self.relationship_kind,
            self.component_id,
            self.description,
            self.technology,
            self.landscape_domain_id,
            self.parent_domain_id,
            self.product.to_domain() if self.product else None,
            self.journey.to_domain() if self.journey else None,
        )


class CandidateCitationResponse(BaseModel):
    location: str
    quote: str


class PossibleMatchResponse(BaseModel):
    """An existing system a name in the suggestion may mean; a maintainer confirms it."""

    role: MatchRole
    written_as: str
    system_id: str
    system_name: str
    reason: str

    @classmethod
    def from_domain(cls, match: PossibleMatch, names: dict[str, str]) -> PossibleMatchResponse:
        return cls(
            role=match.role,
            written_as=match.written_as,
            system_id=match.system_id,
            system_name=names.get(match.system_id, match.system_id),
            reason=match.reason,
        )


class CatalogueSuggestionResponse(BaseModel):
    id: str
    document_version_id: str
    content: CandidateContentSchema
    citations: list[CandidateCitationResponse]
    match: CandidateMatch
    status: CandidateStatus
    edited: bool
    model: str
    prompt_version: str
    created_at: datetime
    decided_by: str | None
    decided_at: datetime | None
    # Stated outright by the document, or inferred from what it describes.
    basis: CandidateBasis
    rationale: str | None
    possible_matches: list[PossibleMatchResponse]
    # Names of the draft systems the suggestion's references resolve to, by any of their
    # names; null when the system is not in the draft yet.
    system_name: str | None
    target_system_name: str | None

    @classmethod
    def from_domain(cls, view: CandidateView, names: dict[str, str]) -> CatalogueSuggestionResponse:
        """``names`` are the draft's system names by id, to name each possible match."""
        item = view.candidate
        return cls(
            id=item.id,
            document_version_id=item.document_version_id,
            content=CandidateContentSchema.from_domain(item.content),
            citations=[
                CandidateCitationResponse(location=citation.location, quote=citation.quote)
                for citation in item.citations
            ],
            match=view.match,
            status=item.status,
            edited=item.edited,
            model=item.model,
            prompt_version=item.prompt_version,
            created_at=item.created_at,
            decided_by=item.decided_by,
            decided_at=item.decided_at,
            basis=item.basis,
            rationale=item.rationale,
            # Once the name a match is for is in the draft, that match has been decided.
            possible_matches=[
                PossibleMatchResponse.from_domain(match, names) for match in view.open_matches
            ],
            system_name=view.system_name,
            target_system_name=view.target_name,
        )


class ExtractionRunResponse(BaseModel):
    id: str
    document_version_id: str
    model: str
    prompt_version: str
    candidate_count: int
    warnings: list[str]
    created_at: datetime
    match_model: str | None
    match_prompt_version: str | None

    @classmethod
    def from_domain(cls, run: ExtractionRun) -> ExtractionRunResponse:
        return cls(
            id=run.id,
            document_version_id=run.document_version_id,
            model=run.model,
            prompt_version=run.prompt_version,
            candidate_count=run.candidate_count,
            warnings=list(run.warnings),
            created_at=run.created_at,
            match_model=run.match_model,
            match_prompt_version=run.match_prompt_version,
        )


class CatalogueSuggestionsResponse(BaseModel):
    release_id: str
    release_revision: int
    suggestions: list[CatalogueSuggestionResponse]
    runs: list[ExtractionRunResponse]

    @classmethod
    def from_domain(cls, overview: CandidateOverview) -> CatalogueSuggestionsResponse:
        names = {system.id: system.name for system in overview.release.systems}
        return cls(
            release_id=overview.release.id,
            release_revision=overview.release.revision,
            suggestions=[
                CatalogueSuggestionResponse.from_domain(item, names) for item in overview.candidates
            ],
            runs=[ExtractionRunResponse.from_domain(item) for item in overview.runs],
        )


class SuggestionDecisionRequest(RevisionRequest):
    accept: bool
    # Present when the maintainer edited the suggestion before accepting it.
    content: CandidateContentSchema | None = None


class AcceptAllResponse(BaseModel):
    release: KnowledgeReleaseResponse
    remaining: int


class DocumentExtractionResponse(BaseModel):
    document_version_id: str
    job: ArchitectureJobResponse


class SampleRequirementSchema(BaseModel):
    """A sample requirement; omit `id` for a new one and the server assigns it."""

    id: Identifier | None = None
    text: Text


class SampleRequirementsRequest(RevisionRequest):
    items: list[SampleRequirementSchema] = Field(max_length=MAX_SAMPLES)


class SampleRequirementsResponse(BaseModel):
    revision: int
    items: list[SampleRequirementSchema]
    updated_by: str | None
    updated_at: datetime | None

    @classmethod
    def from_domain(cls, samples: SampleRequirementSet) -> SampleRequirementsResponse:
        return cls(
            revision=samples.revision,
            items=[SampleRequirementSchema(id=item.id, text=item.text) for item in samples.items],
            updated_by=samples.updated_by,
            updated_at=samples.updated_at,
        )


class ComparedSystemResponse(BaseModel):
    id: str
    name: str


class ComparedImpactResponse(BaseModel):
    release_id: str
    systems: list[ComparedSystemResponse]
    uncertainty: str | None

    @classmethod
    def from_domain(cls, impact: ComparedImpact) -> ComparedImpactResponse:
        return cls(
            release_id=impact.release_id,
            systems=[ComparedSystemResponse(id=item[0], name=item[1]) for item in impact.systems],
            uncertainty=impact.uncertainty,
        )


class ImpactComparisonResponse(BaseModel):
    query: str
    in_use: ComparedImpactResponse
    this_version: ComparedImpactResponse

    @classmethod
    def from_domain(cls, comparison: ImpactComparison) -> ImpactComparisonResponse:
        return cls(
            query=comparison.query,
            in_use=ComparedImpactResponse.from_domain(comparison.in_use),
            this_version=ComparedImpactResponse.from_domain(comparison.this_version),
        )


class MappingImpactResponse(BaseModel):
    """How much of the backlog is mapped, and how much uses an older catalogue version."""

    active_release_id: str
    requirements: int
    features: int
    stories: int
    outdated_requirements: int
    outdated_features: int
    outdated_stories: int

    @classmethod
    def from_domain(cls, impact: MappingImpact) -> MappingImpactResponse:
        return cls(
            active_release_id=impact.active_release_id,
            requirements=impact.requirements,
            features=impact.features,
            stories=impact.stories,
            outdated_requirements=impact.outdated_requirements,
            outdated_features=impact.outdated_features,
            outdated_stories=impact.outdated_stories,
        )


class RejectSuggestionsRequest(RevisionRequest):
    suggestion_ids: list[Identifier] = Field(max_length=MAX_CATALOGUE_ITEMS)


class RejectSuggestionsResponse(BaseModel):
    rejected: int


class PassageResponse(BaseModel):
    location: str
    text: str


class DocumentPassageResponse(BaseModel):
    mime_type: str
    passage: PassageResponse
    before: list[PassageResponse]
    after: list[PassageResponse]

    @classmethod
    def from_domain(cls, found: DocumentPassage) -> DocumentPassageResponse:
        def one(item: LocatedText) -> PassageResponse:
            return PassageResponse(location=item.location, text=item.text)

        return cls(
            mime_type=found.mime_type,
            passage=one(found.passage),
            before=[one(item) for item in found.before],
            after=[one(item) for item in found.after],
        )
