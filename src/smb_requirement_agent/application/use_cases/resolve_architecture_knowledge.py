"""Map against one pinned published release and its indexed evidence.

Systems come from the architecture release; who owns them (squads, value
streams and products) comes from the organisation catalogue at mapping time.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureKnowledgePort,
    ArchitectureQuery,
)
from smb_requirement_agent.application.ports.architecture_knowledge_repository import (
    ArchitectureKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.architecture_rag import (
    ArchitectureEvidenceError,
    ArchitectureEvidenceIndexPort,
    ArchitectureReasonerPort,
)
from smb_requirement_agent.application.ports.organisation_repository import (
    OrganisationRepositoryPort,
)
from smb_requirement_agent.application.use_cases.architecture_evidence import (
    gather_evidence,
    named_systems,
)
from smb_requirement_agent.application.use_cases.capability_domain_fallback import (
    suggest_domains,
)
from smb_requirement_agent.application.use_cases.impact_product_context import (
    journey_steps,
    product_contexts,
)
from smb_requirement_agent.domain.architecture.entities import (
    ArchitectureCitation,
    ArchitectureDependency,
    OrganisationReference,
    SystemCapability,
    SystemReference,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    KnowledgeConflictError,
    KnowledgeReleaseStatus,
    SystemDefinition,
)
from smb_requirement_agent.domain.architecture.neighbours import adjacent


def _reference(item: SystemDefinition) -> SystemReference:
    return SystemReference(
        item.id,
        item.name,
        True,
        tuple(SystemCapability(cap.id, cap.name) for cap in item.capabilities),
        item.constraints,
    )


class ResolveArchitectureKnowledge(ArchitectureKnowledgePort):
    def __init__(
        self,
        repository: ArchitectureKnowledgeRepositoryPort,
        index: ArchitectureEvidenceIndexPort,
        reasoner: ArchitectureReasonerPort,
        initial: ArchitectureKnowledgePort,
        organisation: OrganisationRepositoryPort,
    ) -> None:
        self._repository = repository
        self._index = index
        self._reasoner = reasoner
        self._initial = initial
        self._organisation = organisation

    def match(self, query: ArchitectureQuery) -> ArchitectureKnowledgeMatch:
        release, matched = self._match_systems(query)
        catalogue = self._organisation.load()

        def owned(system: SystemReference) -> SystemReference:
            if not system.catalogued:
                return system
            ownership = catalogue.ownership(system.id)
            return replace(
                system,
                squads=tuple(
                    OrganisationReference(item.id, item.name) for item in ownership.squads
                ),
                value_streams=tuple(
                    OrganisationReference(item.id, item.name) for item in ownership.value_streams
                ),
                products=tuple(
                    OrganisationReference(item.id, item.name) for item in ownership.products
                ),
            )

        mapped = {item.id for item in matched.systems if item.catalogued}
        nearby = adjacent(mapped, release.relationships)
        systems = {item.id: item for item in release.systems}

        def placed(system: SystemReference) -> SystemReference:
            """The system with each capability's domain and component as the pinned release
            places it."""
            if not system.catalogued or system.id not in systems:
                return system
            definition = systems[system.id]
            pinned = {cap.id: cap for cap in definition.capabilities}

            def place(capability: SystemCapability) -> SystemCapability:
                found = pinned.get(capability.id)
                domain_id = found.domain_id if found else None
                component = definition.component(found.component_id if found else None)
                return replace(
                    capability,
                    domain_id=domain_id,
                    domain_path=tuple(item.name for item in release.domain_path(domain_id)),
                    component_id=component.id if component else None,
                    component_name=component.name if component else None,
                )

            return replace(system, capabilities=tuple(place(item) for item in system.capabilities))

        text = " ".join(query.text)
        contexts = product_contexts(release, text)
        return replace(
            matched,
            systems=tuple(owned(placed(system)) for system in matched.systems),
            adjacent_systems=tuple(
                owned(placed(_reference(systems[system_id]))) for system_id in nearby.system_ids
            ),
            adjacent_dependencies=nearby.dependencies,
            adjacent_omitted=nearby.omitted,
            suggested_domains=() if mapped else suggest_domains(release, text),
            product_contexts=contexts,
            journey_steps=journey_steps(release, mapped, contexts),
        )

    def _match_systems(
        self, query: ArchitectureQuery
    ) -> tuple[ArchitectureKnowledge, ArchitectureKnowledgeMatch]:
        release = (
            self._repository.get(query.release_id)
            if query.release_id
            else self._repository.active()
        )
        if release is None or release.status is not KnowledgeReleaseStatus.PUBLISHED:
            raise KnowledgeConflictError("The selected architecture release is unavailable.")
        if release.id == "smb-source-reference-v1":
            return release, self._initial.match(query)
        if release.built_revision != release.revision:
            raise KnowledgeConflictError("The published release has no complete evidence index.")
        if release.index_profile != self._index.profile:
            raise KnowledgeConflictError(
                "The architecture embedding profile changed; rebuild a draft."
            )
        text = " ".join(query.text)
        evidence = gather_evidence(self._index, release, release.index_id or release.id, text)
        selected = self._reasoner.select(query, release, evidence)
        catalogue = {item.id: item for item in release.systems}
        ids = set(selected.system_ids)
        citation_ids = list(selected.citation_ids)
        citations = list(selected.citations)
        for system in named_systems(release, text):
            support = next(
                (
                    chunk
                    for chunk in evidence
                    if chunk.document_version_id is None
                    and (
                        chunk.location == f"system {system.id}"
                        or chunk.location.startswith(f"system {system.id},")
                    )
                ),
                None,
            )
            if support is not None:
                ids.add(system.id)
                citation_ids.append(support.id)
                citations.append(ArchitectureCitation(system.id, support.id, support.text))
        systems: list[SystemReference] = []
        for raw in query.declared_systems:
            key = raw.strip().casefold()
            if not key:
                continue
            known = next(
                (
                    system
                    for system in release.systems
                    if key
                    in {
                        value.casefold()
                        for value in (system.id, system.name, system.name_ar or "", *system.aliases)
                    }
                ),
                None,
            )
            if known is not None:
                ids.add(known.id)
            else:
                unknown_id = "declared-" + hashlib.sha256(key.encode()).hexdigest()[:12]
                systems.append(SystemReference(unknown_id, raw.strip(), False))
        for system_id in sorted(ids):
            item = catalogue.get(system_id)
            if item is None:
                raise ArchitectureEvidenceError("Reasoner selected an unknown system.")
            systems.append(_reference(item))
        dependencies = tuple(
            ArchitectureDependency(
                item.source_system_id, item.target_system_id, item.description, item.kind
            )
            for item in release.relationships
            if item.source_system_id in ids and item.target_system_id in ids
        )
        uncertainty = selected.uncertainty
        if ids and uncertainty == "Insufficient evidence to identify a catalogue system.":
            uncertainty = None
        return release, ArchitectureKnowledgeMatch(
            release.id,
            tuple(systems),
            dependencies,
            tuple(dict.fromkeys(citation_ids)),
            uncertainty,
            self._reasoner.model,
            self._index.embedding_model,
            "architecture-impact-v1",
            release.built_revision,
            "ai_inference",
            tuple(dict.fromkeys(citations)),
        )
