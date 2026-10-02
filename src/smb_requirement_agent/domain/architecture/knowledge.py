"""Versioned, human-maintained architecture knowledge."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Protocol

# Re-exported: the rest of the codebase imports the error from here.
from smb_requirement_agent.domain.architecture.invariants import (
    InvalidKnowledgeError as InvalidKnowledgeError,
)
from smb_requirement_agent.domain.architecture.invariants import required
from smb_requirement_agent.domain.architecture.journeys import Journey, check_journeys
from smb_requirement_agent.domain.architecture.products import ProductOffering, check_offerings


class KnowledgeReleaseStatus(StrEnum):
    """A draft is edited by maintainers; a published release is immutable."""

    DRAFT = "draft"
    PUBLISHED = "published"


class KnowledgeConflictError(Exception):
    """A draft changed while an editor was working."""


@dataclass(frozen=True)
class KnowledgeAuditEvent:
    release_id: str
    actor_id: str
    action: str
    revision: int
    rationale: str | None
    created_at: datetime


_required = required


MAX_DOMAIN_DEPTH = 3


@dataclass(frozen=True)
class CapabilityDomain:
    """A business area capabilities belong to, such as "Order capture" (ADR-0089).

    Domains form a shallow tree maintained with the release. They group what
    systems do; they never select a system on their own.
    """

    id: str
    name: str
    name_ar: str | None = None
    parent_id: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        _check_node(self, "Domain")


@dataclass(frozen=True)
class LandscapeDomain:
    """Where a system sits in the architecture landscape, such as "Customer › Assisted" (ADR-0094).

    A separate tree from capability domains: a system sits in one landscape
    domain, while its capabilities may serve several business areas. A
    sub-domain is a child. Like capability domains, it never selects a system.
    """

    id: str
    name: str
    name_ar: str | None = None
    parent_id: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        _check_node(self, "Landscape domain")


class _Node(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def name_ar(self) -> str | None: ...

    @property
    def parent_id(self) -> str | None: ...

    @property
    def description(self) -> str | None: ...


def _check_node(node: _Node, noun: str) -> None:
    _required(node.id, f"{noun} id")
    _required(node.name, f"{noun} name")
    for value, label in (
        (node.name_ar, f"Arabic {noun.casefold()} name"),
        (node.parent_id, f"Parent {noun.casefold()}"),
        (node.description, f"{noun} description"),
    ):
        if value is not None:
            _required(value, label)
    if node.parent_id == node.id:
        raise InvalidKnowledgeError(f"A {noun.casefold()} cannot be its own parent.")


def _check_domains[NodeT: _Node](
    domains: tuple[NodeT, ...], noun: str = "Domain"
) -> dict[str, NodeT]:
    """Unique ids, known parents, no cycles, at most three levels, sibling names unique."""
    by_id = {item.id: item for item in domains}
    if len(by_id) != len(domains):
        raise InvalidKnowledgeError(f"{noun} ids must be unique.")
    siblings: set[tuple[str | None, str]] = set()
    lower = noun.casefold()
    for item in domains:
        if item.parent_id is not None and item.parent_id not in by_id:
            raise InvalidKnowledgeError(
                f"{noun} {item.name!r} names a parent that is not in the catalogue."
            )
        key = (item.parent_id, item.name.casefold().strip())
        if key in siblings:
            raise InvalidKnowledgeError(f"Two {lower}s under one parent are named {item.name!r}.")
        siblings.add(key)
        depth, seen, current = 1, {item.id}, item
        while current.parent_id is not None:
            current = by_id[current.parent_id]
            if current.id in seen:
                raise InvalidKnowledgeError(f"{noun} {item.name!r} is inside itself.")
            seen.add(current.id)
            depth += 1
        if depth > MAX_DOMAIN_DEPTH:
            raise InvalidKnowledgeError(
                f"{noun}s are at most {MAX_DOMAIN_DEPTH} levels deep; {item.name!r} is deeper."
            )
    return by_id


@dataclass(frozen=True)
class KnowledgeCapability:
    id: str
    name: str
    triggers: tuple[str, ...]
    # The capability domain it belongs to; None while nobody has placed it.
    domain_id: str | None = None
    # The component of its system that delivers it (ADR-0092); None when the
    # system has no components or nobody has placed it.
    component_id: str | None = None

    def __post_init__(self) -> None:
        if self.domain_id is not None:
            _required(self.domain_id, "Capability domain")
        if self.component_id is not None:
            _required(self.component_id, "Capability component")
        _required(self.id, "Capability id")
        _required(self.name, "Capability name")
        if not self.triggers or any(not item.strip() for item in self.triggers):
            raise InvalidKnowledgeError("A capability needs non-empty matching phrases.")


@dataclass(frozen=True)
class SystemComponent:
    """A named part of a system, such as a module or service (ADR-0092).

    Components organise what a system does; they never select a system, so
    their names and aliases take no part in matching.
    """

    id: str
    name: str
    name_ar: str | None = None
    description: str | None = None
    aliases: tuple[str, ...] = ()
    # What it is built as, in the maintainer's words: "Microservice", "Batch job".
    technology: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "Component id")
        _required(self.name, "Component name")
        for value, label in (
            (self.name_ar, "Arabic component name"),
            (self.description, "Component description"),
            (self.technology, "Component technology"),
        ):
            if value is not None:
                _required(value, label)
        if any(not value.strip() for value in self.aliases):
            raise InvalidKnowledgeError("Component aliases must not be blank.")

    @property
    def labels(self) -> tuple[str, ...]:
        return (self.name, *((self.name_ar,) if self.name_ar else ()), *self.aliases)


@dataclass(frozen=True)
class SystemDefinition:
    id: str
    name: str
    aliases: tuple[str, ...] = ()
    capabilities: tuple[KnowledgeCapability, ...] = ()
    constraints: tuple[str, ...] = ()
    name_ar: str | None = None
    components: tuple[SystemComponent, ...] = ()
    # What the system is for, in a sentence or two; None while nobody has said.
    description: str | None = None
    # The landscape domain or sub-domain it sits in (ADR-0094); None while unplaced.
    landscape_domain_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.id, "System id")
        _required(self.name, "System name")
        for value, label in (
            (self.name_ar, "Arabic system name"),
            (self.description, "System description"),
            (self.landscape_domain_id, "System landscape domain"),
        ):
            if value is not None:
                _required(value, label)
        if any(not value.strip() for value in (*self.aliases, *self.constraints)):
            raise InvalidKnowledgeError("System aliases and constraints must not be blank.")
        labels = (self.name, *((self.name_ar,) if self.name_ar else ()), *self.aliases)
        if len({value.casefold().strip() for value in labels}) != len(labels):
            raise InvalidKnowledgeError("System names and aliases must be unique.")
        if len({item.id for item in self.capabilities}) != len(self.capabilities):
            raise InvalidKnowledgeError("Capability ids must be unique within a system.")
        if len({item.id for item in self.components}) != len(self.components):
            raise InvalidKnowledgeError(f"{self.name}: component ids must be unique.")
        seen: set[str] = set()
        for component in self.components:
            for label in component.labels:
                key = label.casefold().strip()
                if key in seen:
                    raise InvalidKnowledgeError(
                        f"{self.name}: {label!r} names more than one component. Each name or "
                        "alias must identify one component."
                    )
                seen.add(key)
        component_ids = {item.id for item in self.components}
        for capability in self.capabilities:
            if capability.component_id is not None and capability.component_id not in component_ids:
                raise InvalidKnowledgeError(
                    f"{self.name}: {capability.name} is placed in a component that is not in "
                    "the system."
                )

    def component(self, component_id: str | None) -> SystemComponent | None:
        return next((item for item in self.components if item.id == component_id), None)


class RelationshipKind(StrEnum):
    """How the source system depends on the target, when a source says so."""

    CALLS_API = "calls_api"
    PUBLISHES_EVENTS_TO = "publishes_events_to"
    TRANSFERS_DATA_TO = "transfers_data_to"
    ORCHESTRATES = "orchestrates"
    UNSPECIFIED = "unspecified"


def relationship_kind(value: str | RelationshipKind) -> RelationshipKind:
    """A stored or transported kind; anything unknown is refused, never guessed."""
    try:
        return RelationshipKind(value)
    except ValueError as exc:
        raise InvalidKnowledgeError(f"Unknown relationship kind {value!r}.") from exc


@dataclass(frozen=True)
class SystemRelationship:
    source_system_id: str
    target_system_id: str
    description: str
    # An attribute of the relationship, not part of its identity: changing it is
    # an edit. Relationships recorded before kinds existed are unspecified.
    kind: RelationshipKind = RelationshipKind.UNSPECIFIED

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", relationship_kind(self.kind))
        _required(self.source_system_id, "Relationship source")
        _required(self.target_system_id, "Relationship target")
        _required(self.description, "Relationship description")
        if self.source_system_id == self.target_system_id:
            raise InvalidKnowledgeError("A system cannot depend on itself.")


@dataclass(frozen=True)
class KnowledgeDocumentVersion:
    id: str
    title: str
    filename: str
    mime_type: str
    language: str
    checksum: str
    storage_key: str
    uploaded_by: str
    uploaded_at: datetime

    def __post_init__(self) -> None:
        for label, value in (
            ("Document id", self.id),
            ("Title", self.title),
            ("Filename", self.filename),
            ("Checksum", self.checksum),
            ("Actor", self.uploaded_by),
        ):
            _required(value, label)
        if self.language not in {"en", "ar", "mixed"}:
            raise InvalidKnowledgeError("Document language must be en, ar, or mixed.")
        if self.uploaded_at.tzinfo is None:
            raise InvalidKnowledgeError("Document timestamp must have a timezone.")


MAX_VERSION_NAME = 80


def version_name(value: str) -> str:
    """A version's name: required, trimmed, at most MAX_VERSION_NAME characters."""
    name = " ".join(value.split())
    if not name:
        raise InvalidKnowledgeError("Give the version a name.")
    if len(name) > MAX_VERSION_NAME:
        raise InvalidKnowledgeError(f"A version name is at most {MAX_VERSION_NAME} characters.")
    return name


@dataclass(frozen=True)
class ArchitectureKnowledge:
    id: str
    revision: int
    systems: tuple[SystemDefinition, ...]
    relationships: tuple[SystemRelationship, ...]
    documents: tuple[KnowledgeDocumentVersion, ...] = ()
    status: KnowledgeReleaseStatus = KnowledgeReleaseStatus.DRAFT
    built_revision: int | None = None
    published_at: datetime | None = None
    published_by: str | None = None
    index_profile: str | None = None
    index_hash: str | None = None
    index_id: str | None = None
    # What people call this version, and who started it. None only on releases
    # recorded before versions were named.
    name: str | None = None
    created_by: str | None = None
    capability_domains: tuple[CapabilityDomain, ...] = ()
    landscape_domains: tuple[LandscapeDomain, ...] = ()
    # Commercial offerings and the systems that deliver their components (ADR-0095).
    products: tuple[ProductOffering, ...] = ()
    # The activities that fulfil an offering's orders, and who performs them (ADR-0096).
    journeys: tuple[Journey, ...] = ()

    def __post_init__(self) -> None:
        _required(self.id, "Knowledge id")
        if self.name is not None:
            object.__setattr__(self, "name", version_name(self.name))
        try:
            # Stored and transported releases carry the plain value.
            object.__setattr__(self, "status", KnowledgeReleaseStatus(self.status))
        except ValueError as exc:
            raise InvalidKnowledgeError("Invalid knowledge revision or status.") from exc
        if self.revision < 1:
            raise InvalidKnowledgeError("Invalid knowledge revision or status.")
        system_ids = {item.id for item in self.systems}
        if len(system_ids) != len(self.systems):
            raise InvalidKnowledgeError("System ids must be unique.")
        owners: dict[str, SystemDefinition] = {}
        for system in self.systems:
            for alias in (system.id, system.name, system.name_ar or "", *system.aliases):
                if not alias:
                    continue
                owner = owners.setdefault(alias.casefold().strip(), system)
                if owner.id != system.id:
                    raise InvalidKnowledgeError(
                        f"{alias!r} already names {owner.name}, so it cannot also name "
                        f"{system.name}. Each name or alias must identify one system."
                    )
        if any(
            item.source_system_id not in system_ids or item.target_system_id not in system_ids
            for item in self.relationships
        ):
            raise InvalidKnowledgeError("Relationships must connect catalogued systems.")
        relationship_keys = [
            (item.source_system_id, item.target_system_id, item.description.casefold())
            for item in self.relationships
        ]
        if len(set(relationship_keys)) != len(relationship_keys):
            raise InvalidKnowledgeError("Relationships must be unique.")
        if len({item.id for item in self.documents}) != len(self.documents):
            raise InvalidKnowledgeError("Document version ids must be unique.")
        domains = _check_domains(self.capability_domains)
        for system in self.systems:
            for capability in system.capabilities:
                if capability.domain_id is not None and capability.domain_id not in domains:
                    raise InvalidKnowledgeError(
                        f"{system.name}: {capability.name} is placed in a domain that is not "
                        "in the catalogue."
                    )
        check_offerings(self.products, system_ids)
        check_journeys(self.journeys, system_ids, self.products)
        landscape = _check_domains(self.landscape_domains, "Landscape domain")
        for system in self.systems:
            if (
                system.landscape_domain_id is not None
                and system.landscape_domain_id not in landscape
            ):
                raise InvalidKnowledgeError(
                    f"{system.name} is placed in a landscape domain that is not in the catalogue."
                )
        if self.status is KnowledgeReleaseStatus.PUBLISHED and (
            self.published_at is None or not self.published_by
        ):
            raise InvalidKnowledgeError("Published releases require an actor and timestamp.")

    def updated(
        self,
        *,
        systems: tuple[SystemDefinition, ...] | None = None,
        relationships: tuple[SystemRelationship, ...] | None = None,
        documents: tuple[KnowledgeDocumentVersion, ...] | None = None,
        capability_domains: tuple[CapabilityDomain, ...] | None = None,
        landscape_domains: tuple[LandscapeDomain, ...] | None = None,
        products: tuple[ProductOffering, ...] | None = None,
        journeys: tuple[Journey, ...] | None = None,
    ) -> ArchitectureKnowledge:
        if self.status is not KnowledgeReleaseStatus.DRAFT:
            raise KnowledgeConflictError("Published knowledge is immutable.")
        return replace(
            self,
            revision=self.revision + 1,
            built_revision=None,
            index_profile=None,
            index_hash=None,
            index_id=None,
            systems=self.systems if systems is None else systems,
            relationships=self.relationships if relationships is None else relationships,
            documents=self.documents if documents is None else documents,
            capability_domains=(
                self.capability_domains if capability_domains is None else capability_domains
            ),
            landscape_domains=(
                self.landscape_domains if landscape_domains is None else landscape_domains
            ),
            products=self.products if products is None else products,
            journeys=self.journeys if journeys is None else journeys,
        )

    def domain_path(self, domain_id: str | None) -> tuple[CapabilityDomain, ...]:
        """A domain and its ancestors, from the top of the tree down; empty when unplaced."""
        by_id = {item.id: item for item in self.capability_domains}
        path: list[CapabilityDomain] = []
        current = by_id.get(domain_id or "")
        while current is not None:
            path.insert(0, current)
            current = by_id.get(current.parent_id or "")
        return tuple(path)

    def landscape_path(self, domain_id: str | None) -> tuple[LandscapeDomain, ...]:
        """A landscape domain and its ancestors, from the top down; empty when unplaced."""
        by_id = {item.id: item for item in self.landscape_domains}
        path: list[LandscapeDomain] = []
        current = by_id.get(domain_id or "")
        while current is not None:
            path.insert(0, current)
            current = by_id.get(current.parent_id or "")
        return tuple(path)
