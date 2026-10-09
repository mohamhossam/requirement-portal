"""Snapshot mappings for breakdown's value types: Story quality and architecture impact."""

from __future__ import annotations

from datetime import datetime

from smb_requirement_agent.breakdown.domain.architecture.entities import ArchitectureImpact
from smb_requirement_agent.breakdown.domain.story.quality import (
    FindingSource,
    InvestAssessment,
    InvestCriterion,
    ValidationFinding,
)
from smb_requirement_agent.breakdown.domain.story.value_objects import (
    StoryId,
)
from smb_requirement_agent.infrastructure.persistence.payload_fields import (
    JsonObject,
    boolean_field,
    json_array,
    json_object,
    nullable_text,
    optional_json_array,
    required_text,
)
from smb_requirement_agent.references.domain.architecture.catalogue import (
    ArchitectureCitation,
    ArchitectureDependency,
    DomainSuggestion,
    JourneyNeighbour,
    JourneyStep,
    OfferingDuty,
    OrganisationReference,
    ProductContext,
    SystemCapability,
    SystemReference,
)
from smb_requirement_agent.references.domain.architecture.knowledge import RelationshipKind
from smb_requirement_agent.shared_kernel.generation import Provenance


def quality_assessment_from_payload(data: JsonObject) -> InvestAssessment:
    provenance = json_object(data["provenance"])
    return InvestAssessment(
        StoryId(required_text(data, "story_id")),
        tuple(
            ValidationFinding(
                InvestCriterion(required_text(json_object(item), "criterion")),
                boolean_field(json_object(item), "passed"),
                required_text(json_object(item), "message"),
                FindingSource(required_text(json_object(item), "source")),
            )
            for item in json_array(data, "findings")
        ),
        Provenance(
            datetime.fromisoformat(required_text(provenance, "generated_at")),
            required_text(provenance, "model"),
            required_text(provenance, "prompt_version"),
        ),
    )


def quality_assessment_to_payload(value: InvestAssessment) -> JsonObject:
    return {
        "story_id": value.story_id.value,
        "findings": [
            {
                "criterion": finding.criterion.value,
                "passed": finding.passed,
                "message": finding.message,
                "source": finding.source.value,
            }
            for finding in value.findings
        ],
        "provenance": {
            "generated_at": value.provenance.generated_at.isoformat(),
            "model": value.provenance.model,
            "prompt_version": value.provenance.prompt_version,
        },
    }


def _references_to_payload(values: tuple[OrganisationReference, ...]) -> list[JsonObject]:
    return [{"id": item.id, "name": item.name} for item in values]


def _references_from_payload(data: JsonObject, key: str) -> tuple[OrganisationReference, ...]:
    return tuple(
        OrganisationReference(
            required_text(json_object(item), "id"), required_text(json_object(item), "name")
        )
        for item in optional_json_array(data, key)
    )


def _capability_to_payload(capability: SystemCapability) -> JsonObject:
    payload: JsonObject = {"id": capability.id, "name": capability.name}
    if capability.domain_id is not None:
        payload["domain_id"] = capability.domain_id
        payload["domain_path"] = list(capability.domain_path)
    if capability.component_id is not None:
        payload["component_id"] = capability.component_id
        payload["component_name"] = capability.component_name
    return payload


def _capability_from_payload(raw: object) -> SystemCapability:
    data = json_object(raw)
    return SystemCapability(
        required_text(data, "id"),
        required_text(data, "name"),
        nullable_text(data, "domain_id"),
        tuple(str(item) for item in optional_json_array(data, "domain_path")),
        nullable_text(data, "component_id"),
        nullable_text(data, "component_name"),
    )


def _system_to_payload(system: SystemReference) -> JsonObject:
    return {
        "id": system.id,
        "name": system.name,
        "catalogued": system.catalogued,
        "capabilities": [_capability_to_payload(capability) for capability in system.capabilities],
        "constraints": list(system.constraints),
        "squads": _references_to_payload(system.squads),
        "value_streams": _references_to_payload(system.value_streams),
        "products": _references_to_payload(system.products),
    }


def _dependency_to_payload(dependency: ArchitectureDependency) -> JsonObject:
    payload: JsonObject = {
        "source_system_id": dependency.source_system_id,
        "target_system_id": dependency.target_system_id,
        "description": dependency.description,
    }
    if dependency.kind is not RelationshipKind.UNSPECIFIED:
        payload["kind"] = dependency.kind.value
    return payload


def architecture_to_payload(value: ArchitectureImpact | None) -> object:
    if value is None:
        return None
    payload: JsonObject = {
        "knowledge_version": value.knowledge_version,
        "citation_ids": list(value.citation_ids),
        "citations": [
            {"system_id": item.system_id, "chunk_id": item.chunk_id, "quote": item.quote}
            for item in value.citations
        ],
        "uncertainty": value.uncertainty,
        "model": value.model,
        "embedding_model": value.embedding_model,
        "prompt_version": value.prompt_version,
        "index_revision": value.index_revision,
        "evidence_classification": value.evidence_classification,
        "mapped_at": value.mapped_at.isoformat(),
        "systems": [_system_to_payload(system) for system in value.systems],
        "dependencies": [_dependency_to_payload(item) for item in value.dependencies],
    }
    # Written only when present, so impacts without connected systems keep their shape.
    if value.adjacent_systems:
        payload["adjacent_systems"] = [_system_to_payload(item) for item in value.adjacent_systems]
        payload["adjacent_dependencies"] = [
            _dependency_to_payload(item) for item in value.adjacent_dependencies
        ]
    if value.adjacent_omitted:
        payload["adjacent_omitted"] = value.adjacent_omitted
    if value.suggested_domains:
        payload["suggested_domains"] = [
            {
                "domain_id": item.domain_id,
                "path": list(item.path),
                "system_ids": list(item.system_ids),
                "matched_terms": list(item.matched_terms),
                "system_names": list(item.system_names),
            }
            for item in value.suggested_domains
        ]
    if value.product_contexts:
        payload["product_contexts"] = [
            {
                "product_id": item.product_id,
                "product_name": item.product_name,
                "matched_terms": list(item.matched_terms),
                "order_type": item.order_type,
                "responsibilities": [
                    {
                        "component_id": duty.component_id,
                        "component_name": duty.component_name,
                        "system_id": duty.system_id,
                        "system_name": duty.system_name,
                        "role": duty.role,
                        "description": duty.description,
                    }
                    for duty in item.responsibilities
                ],
            }
            for item in value.product_contexts
        ]
    if value.journey_steps:
        payload["journey_steps"] = [
            {
                "system_id": item.system_id,
                "journey_id": item.journey_id,
                "journey_name": item.journey_name,
                "number": item.number,
                "name": item.name,
                "performs": item.performs,
                "fulfils": list(item.fulfils),
                "before": [_neighbour_to_payload(other) for other in item.before],
                "after": [_neighbour_to_payload(other) for other in item.after],
            }
            for item in value.journey_steps
        ]
    return payload


def _neighbour_to_payload(item: JourneyNeighbour) -> JsonObject:
    return {
        "number": item.number,
        "name": item.name,
        "system_id": item.system_id,
        "system_name": item.system_name,
    }


def _neighbour_from_payload(raw: object) -> JourneyNeighbour:
    item = json_object(raw)
    return JourneyNeighbour(
        required_text(item, "number"),
        required_text(item, "name"),
        nullable_text(item, "system_id"),
        nullable_text(item, "system_name"),
    )


def _product_context_from_payload(raw: object) -> ProductContext:
    item = json_object(raw)
    return ProductContext(
        required_text(item, "product_id"),
        required_text(item, "product_name"),
        tuple(str(part) for part in json_array(item, "matched_terms")),
        nullable_text(item, "order_type"),
        tuple(
            OfferingDuty(
                required_text(json_object(duty), "component_id"),
                required_text(json_object(duty), "component_name"),
                required_text(json_object(duty), "system_id"),
                required_text(json_object(duty), "system_name"),
                required_text(json_object(duty), "role"),
                str(json_object(duty).get("description", "")),
            )
            for duty in optional_json_array(item, "responsibilities")
        ),
    )


def _journey_step_from_payload(raw: object) -> JourneyStep:
    item = json_object(raw)
    return JourneyStep(
        required_text(item, "system_id"),
        required_text(item, "journey_id"),
        required_text(item, "journey_name"),
        required_text(item, "number"),
        required_text(item, "name"),
        boolean_field(item, "performs"),
        tuple(str(part) for part in optional_json_array(item, "fulfils")),
        tuple(_neighbour_from_payload(other) for other in optional_json_array(item, "before")),
        tuple(_neighbour_from_payload(other) for other in optional_json_array(item, "after")),
    )


def _system_from_payload(raw: object) -> SystemReference:
    system = json_object(raw)
    return SystemReference(
        id=required_text(system, "id"),
        name=required_text(system, "name"),
        catalogued=boolean_field(system, "catalogued"),
        capabilities=tuple(
            _capability_from_payload(capability)
            for capability in json_array(system, "capabilities")
        ),
        constraints=tuple(str(value) for value in optional_json_array(system, "constraints")),
        squads=_references_from_payload(system, "squads"),
        value_streams=_references_from_payload(system, "value_streams"),
        products=_references_from_payload(system, "products"),
    )


def _dependency_from_payload(raw: object) -> ArchitectureDependency:
    item = json_object(raw)
    return ArchitectureDependency(
        required_text(item, "source_system_id"),
        required_text(item, "target_system_id"),
        required_text(item, "description"),
        RelationshipKind(str(item.get("kind", RelationshipKind.UNSPECIFIED.value))),
    )


def architecture_from_payload(raw: object) -> ArchitectureImpact | None:
    if raw is None:
        return None
    data = json_object(raw)
    raw_index_revision = data.get("index_revision")
    index_revision = raw_index_revision if isinstance(raw_index_revision, int) else None
    raw_omitted = data.get("adjacent_omitted")
    adjacent_omitted = raw_omitted if isinstance(raw_omitted, int) else 0
    return ArchitectureImpact(
        knowledge_version=required_text(data, "knowledge_version"),
        mapped_at=datetime.fromisoformat(required_text(data, "mapped_at")),
        systems=tuple(_system_from_payload(item) for item in json_array(data, "systems")),
        dependencies=tuple(
            _dependency_from_payload(item) for item in json_array(data, "dependencies")
        ),
        citation_ids=tuple(str(item) for item in optional_json_array(data, "citation_ids")),
        uncertainty=nullable_text(data, "uncertainty"),
        model=nullable_text(data, "model"),
        embedding_model=nullable_text(data, "embedding_model"),
        prompt_version=nullable_text(data, "prompt_version"),
        index_revision=index_revision,
        evidence_classification=str(data.get("evidence_classification", "legacy_deterministic")),
        citations=tuple(
            ArchitectureCitation(
                required_text(json_object(item), "system_id"),
                required_text(json_object(item), "chunk_id"),
                required_text(json_object(item), "quote"),
            )
            for item in optional_json_array(data, "citations")
        ),
        adjacent_systems=tuple(
            _system_from_payload(item) for item in optional_json_array(data, "adjacent_systems")
        ),
        adjacent_dependencies=tuple(
            _dependency_from_payload(item)
            for item in optional_json_array(data, "adjacent_dependencies")
        ),
        adjacent_omitted=adjacent_omitted,
        suggested_domains=tuple(
            DomainSuggestion(
                required_text(json_object(item), "domain_id"),
                tuple(str(part) for part in json_array(json_object(item), "path")),
                tuple(str(part) for part in json_array(json_object(item), "system_ids")),
                tuple(str(part) for part in json_array(json_object(item), "matched_terms")),
                tuple(str(part) for part in optional_json_array(json_object(item), "system_names")),
            )
            for item in optional_json_array(data, "suggested_domains")
        ),
        product_contexts=tuple(
            _product_context_from_payload(item)
            for item in optional_json_array(data, "product_contexts")
        ),
        journey_steps=tuple(
            _journey_step_from_payload(item) for item in optional_json_array(data, "journey_steps")
        ),
    )
