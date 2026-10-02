"""What a draft changes relative to another release, for review before publishing."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    SystemDefinition,
)
from smb_requirement_agent.domain.architecture.products import ProductOffering

# What a changed offering names, in the order a reviewer reads it.
_OFFERING_FIELDS = (
    "name",
    "code",
    "family",
    "version",
    "lifecycle",
    "proposition",
    "rules",
    "confidence",
    "source",
    "order_types",
    "components",
    "values",
    "audiences",
)


_JOURNEY_FIELDS = (
    "name",
    "product_id",
    "order_type_code",
    "description",
    "confidence",
    "source",
    "activities",
    "flow_rules",
    "integrations",
)


def _bare(offering: ProductOffering) -> tuple[object, ...]:
    """An offering's components without their responsibilities."""
    return tuple(replace(item, responsibilities=()) for item in offering.components)


def _offering_fields(before: ProductOffering, after: ProductOffering) -> tuple[str, ...]:
    """Which parts of an offering changed; a component's responsibilities count as
    "responsibilities", apart from the rest of the component."""
    fields = [
        field
        for field in _OFFERING_FIELDS
        if field != "components" and getattr(before, field) != getattr(after, field)
    ]
    if _bare(before) != _bare(after):
        fields.append("components")
    if [item.responsibilities for item in before.components] != [
        item.responsibilities for item in after.components
    ]:
        fields.append("responsibilities")
    return tuple(fields)


class ChangeKind(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


class ChangedItem(StrEnum):
    SYSTEM = "system"
    CAPABILITY = "capability"
    RELATIONSHIP = "relationship"
    DOCUMENT = "document"
    DOMAIN = "domain"
    COMPONENT = "component"
    LANDSCAPE_DOMAIN = "landscape_domain"
    PRODUCT = "product"
    JOURNEY = "journey"


@dataclass(frozen=True)
class CatalogueChange:
    item: ChangedItem
    change: ChangeKind
    key: str
    label: str
    fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class CatalogueDiff:
    base_release_id: str
    draft_release_id: str
    changes: tuple[CatalogueChange, ...]

    @property
    def empty(self) -> bool:
        return not self.changes


def _system_fields(before: SystemDefinition, after: SystemDefinition) -> tuple[str, ...]:
    fields = []
    if before.name != after.name:
        fields.append("name")
    if before.name_ar != after.name_ar:
        fields.append("name_ar")
    if sorted(before.aliases) != sorted(after.aliases):
        fields.append("aliases")
    if sorted(before.constraints) != sorted(after.constraints):
        fields.append("constraints")
    if before.description != after.description:
        fields.append("description")
    if before.landscape_domain_id != after.landscape_domain_id:
        fields.append("landscape_domain")
    return tuple(fields)


def _keyed_changes[T](
    item: ChangedItem,
    before: dict[str, tuple[str, T]],
    after: dict[str, tuple[str, T]],
) -> list[CatalogueChange]:
    """Items present on only one side; changes to kept items are the caller's concern."""
    changes = [
        CatalogueChange(item, ChangeKind.ADDED, key, label)
        for key, (label, _) in after.items()
        if key not in before
    ]
    changes.extend(
        CatalogueChange(item, ChangeKind.REMOVED, key, label)
        for key, (label, _) in before.items()
        if key not in after
    )
    return changes


def diff_releases(base: ArchitectureKnowledge, draft: ArchitectureKnowledge) -> CatalogueDiff:
    changes: list[CatalogueChange] = []

    base_systems = {item.id: item for item in base.systems}
    draft_systems = {item.id: item for item in draft.systems}
    for system_id, system in draft_systems.items():
        previous = base_systems.get(system_id)
        if previous is None:
            changes.append(
                CatalogueChange(ChangedItem.SYSTEM, ChangeKind.ADDED, system_id, system.name)
            )
            continue
        fields = _system_fields(previous, system)
        if fields:
            changes.append(
                CatalogueChange(
                    ChangedItem.SYSTEM, ChangeKind.CHANGED, system_id, system.name, fields
                )
            )
    changes.extend(
        CatalogueChange(ChangedItem.SYSTEM, ChangeKind.REMOVED, system_id, system.name)
        for system_id, system in base_systems.items()
        if system_id not in draft_systems
    )

    def capabilities(release: ArchitectureKnowledge) -> dict[str, tuple[str, tuple[str, ...]]]:
        return {
            f"{system.id}/{capability.id}": (
                f"{system.name}: {capability.name}",
                (
                    capability.name,
                    capability.domain_id or "",
                    capability.component_id or "",
                    *sorted(capability.triggers),
                ),
            )
            for system in release.systems
            for capability in system.capabilities
        }

    base_capabilities, draft_capabilities = capabilities(base), capabilities(draft)
    changes.extend(_keyed_changes(ChangedItem.CAPABILITY, base_capabilities, draft_capabilities))
    for key, (label, value) in draft_capabilities.items():
        previous_capability = base_capabilities.get(key)
        if previous_capability is None or previous_capability[1] == value:
            continue
        changed = []
        if previous_capability[1][0] != value[0]:
            changed.append("name")
        if previous_capability[1][1] != value[1]:
            changed.append("domain")
        if previous_capability[1][2] != value[2]:
            changed.append("component")
        if previous_capability[1][3:] != value[3:]:
            changed.append("triggers")
        changes.append(
            CatalogueChange(ChangedItem.CAPABILITY, ChangeKind.CHANGED, key, label, tuple(changed))
        )

    def components(
        release: ArchitectureKnowledge,
    ) -> dict[str, tuple[str, tuple[str, str, tuple[str, ...], str, str]]]:
        return {
            f"{system.id}/{component.id}": (
                f"{system.name}: {component.name}",
                (
                    component.name,
                    component.name_ar or "",
                    tuple(sorted(component.aliases)),
                    component.description or "",
                    component.technology or "",
                ),
            )
            for system in release.systems
            for component in system.components
        }

    base_components, draft_components = components(base), components(draft)
    changes.extend(_keyed_changes(ChangedItem.COMPONENT, base_components, draft_components))
    for key, (label, component_value) in draft_components.items():
        previous_component = base_components.get(key)
        if previous_component is None or previous_component[1] == component_value:
            continue
        changes.append(
            CatalogueChange(
                ChangedItem.COMPONENT,
                ChangeKind.CHANGED,
                key,
                label,
                tuple(
                    field
                    for field, before, after in zip(
                        ("name", "name_ar", "aliases", "description", "technology"),
                        previous_component[1],
                        component_value,
                        strict=True,
                    )
                    if before != after
                ),
            )
        )

    def relationships(release: ArchitectureKnowledge) -> dict[str, tuple[str, str]]:
        # The key and label formats are read by the catalogue workbench; the kind is
        # the value, so a changed kind is an edit to the same relationship.
        names = {item.id: item.name for item in release.systems}
        return {
            f"{item.source_system_id}->{item.target_system_id}:{item.description.casefold()}": (
                f"{names.get(item.source_system_id, item.source_system_id)} → "
                f"{names.get(item.target_system_id, item.target_system_id)}: {item.description}",
                item.kind.value,
            )
            for item in release.relationships
        }

    base_relationships, draft_relationships = relationships(base), relationships(draft)
    changes.extend(
        _keyed_changes(ChangedItem.RELATIONSHIP, base_relationships, draft_relationships)
    )
    changes.extend(
        CatalogueChange(ChangedItem.RELATIONSHIP, ChangeKind.CHANGED, key, label, ("kind",))
        for key, (label, kind) in draft_relationships.items()
        if key in base_relationships and base_relationships[key][1] != kind
    )

    def domains(
        release: ArchitectureKnowledge, landscape: bool
    ) -> dict[str, tuple[str, tuple[str, str, str, str]]]:
        tree = release.landscape_domains if landscape else release.capability_domains
        path = release.landscape_path if landscape else release.domain_path
        return {
            item.id: (
                " › ".join(part.name for part in path(item.id)),
                (item.name, item.name_ar or "", item.parent_id or "", item.description or ""),
            )
            for item in tree
        }

    for item, landscape in ((ChangedItem.DOMAIN, False), (ChangedItem.LANDSCAPE_DOMAIN, True)):
        base_domains, draft_domains = domains(base, landscape), domains(draft, landscape)
        changes.extend(_keyed_changes(item, base_domains, draft_domains))
        for key, (label, value) in draft_domains.items():
            previous_domain = base_domains.get(key)
            if previous_domain is None or previous_domain[1] == value:
                continue
            changes.append(
                CatalogueChange(
                    item,
                    ChangeKind.CHANGED,
                    key,
                    label,
                    tuple(
                        field
                        for field, before, after in zip(
                            ("name", "name_ar", "parent", "description"),
                            previous_domain[1],
                            value,
                            strict=True,
                        )
                        if before != after
                    ),
                )
            )
    base_offerings = {item.id: (item.name, item) for item in base.products}
    draft_offerings = {item.id: (item.name, item) for item in draft.products}
    changes.extend(_keyed_changes(ChangedItem.PRODUCT, base_offerings, draft_offerings))
    for key, (label, offering) in draft_offerings.items():
        previous_offering = base_offerings.get(key)
        if previous_offering is None or previous_offering[1] == offering:
            continue
        changes.append(
            CatalogueChange(
                ChangedItem.PRODUCT,
                ChangeKind.CHANGED,
                key,
                label,
                _offering_fields(previous_offering[1], offering),
            )
        )
    base_journeys = {item.id: (item.name, item) for item in base.journeys}
    draft_journeys = {item.id: (item.name, item) for item in draft.journeys}
    changes.extend(_keyed_changes(ChangedItem.JOURNEY, base_journeys, draft_journeys))
    for key, (label, journey) in draft_journeys.items():
        previous_journey = base_journeys.get(key)
        if previous_journey is None or previous_journey[1] == journey:
            continue
        changes.append(
            CatalogueChange(
                ChangedItem.JOURNEY,
                ChangeKind.CHANGED,
                key,
                label,
                tuple(
                    field
                    for field in _JOURNEY_FIELDS
                    if getattr(previous_journey[1], field) != getattr(journey, field)
                ),
            )
        )
    changes.extend(
        _keyed_changes(
            ChangedItem.DOCUMENT,
            {item.id: (item.title, None) for item in base.documents},
            {item.id: (item.title, None) for item in draft.documents},
        )
    )
    return CatalogueDiff(base.id, draft.id, tuple(changes))
