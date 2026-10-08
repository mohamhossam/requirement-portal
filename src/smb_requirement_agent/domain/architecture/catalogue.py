"""The architecture catalogue's content, as requirement work receives and records it.

Systems, their capabilities, dependencies, products, journeys and citations come from the
knowledge service's catalogue (ADR-0099), so they are references' published language. Breakdown's
`ArchitectureImpact` records them as they were at mapping time. They moved here from breakdown's
architecture entities in ADR-0103 PR 15a (F8), with the error they raise.
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.domain.architecture.knowledge import (
    InvalidRelationshipKindError,
    RelationshipKind,
    relationship_kind,
)


class ArchitectureError(Exception):
    """Base error for architecture impact behavior."""


class InvalidArchitectureContentError(ArchitectureError):
    """Raised when architecture knowledge or an impact violates its invariants."""


def _text(value: str, field: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise InvalidArchitectureContentError(f"Architecture {field} must not be blank.")
    return stripped


@dataclass(frozen=True)
class SystemCapability:
    id: str
    name: str
    # The capability's domain in the pinned release, and its names from the top
    # of the tree down. Empty when the capability is not placed in a domain.
    domain_id: str | None = None
    domain_path: tuple[str, ...] = ()
    # The system component that delivers it in the pinned release, with that
    # component's name. Show-only, like the domain (ADR-0092).
    component_id: str | None = None
    component_name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "capability id"))
        object.__setattr__(self, "name", _text(self.name, "capability name"))
        if (self.domain_id is None) != (not self.domain_path):
            raise InvalidArchitectureContentError(
                "A capability domain needs its path, and a path needs its domain."
            )
        if (self.component_id is None) != (self.component_name is None):
            raise InvalidArchitectureContentError(
                "A capability component needs its name, and a name needs its component."
            )
        if self.component_id is not None and self.component_name is not None:
            object.__setattr__(self, "component_id", _text(self.component_id, "component id"))
            object.__setattr__(self, "component_name", _text(self.component_name, "component name"))
        object.__setattr__(
            self, "domain_path", tuple(_text(item, "domain name") for item in self.domain_path)
        )


@dataclass(frozen=True)
class DomainSuggestion:
    """A capability domain whose wording the item matched when no system was found.

    Advice for a reviewer, never mapped impact: it names the systems that do
    work in that domain and the catalogue words that matched.
    """

    domain_id: str
    path: tuple[str, ...]
    system_ids: tuple[str, ...]
    matched_terms: tuple[str, ...]
    # The systems' names as the pinned release gives them, in the order of system_ids.
    system_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.domain_id, "domain id")
        if self.system_names and len(self.system_names) != len(self.system_ids):
            raise InvalidArchitectureContentError("Each suggested system needs its name.")
        if not self.path or not self.matched_terms:
            raise InvalidArchitectureContentError(
                "A domain suggestion needs its path and the words that matched."
            )


@dataclass(frozen=True)
class OfferingDuty:
    """One system's part in delivering one component of a product offering."""

    component_id: str
    component_name: str
    system_id: str
    system_name: str
    role: str
    description: str

    def __post_init__(self) -> None:
        for field in ("component_id", "component_name", "system_id", "system_name", "role"):
            object.__setattr__(self, field, _text(getattr(self, field), field.replace("_", " ")))


@dataclass(frozen=True)
class ProductContext:
    """A product offering the item's text names, and the systems that deliver it (ADR-0097).

    Advice for a reviewer, never mapped impact: the item named the offering, one
    of its components or both, and these are the catalogue's responsibilities
    for what it named, for the order type it named when it named one.
    """

    product_id: str
    product_name: str
    matched_terms: tuple[str, ...]
    order_type: str | None = None
    responsibilities: tuple[OfferingDuty, ...] = ()

    def __post_init__(self) -> None:
        _text(self.product_id, "product offering id")
        _text(self.product_name, "product offering name")
        if not self.matched_terms:
            raise InvalidArchitectureContentError("A product context needs the words that matched.")


@dataclass(frozen=True)
class JourneyNeighbour:
    """An activity just before or after a journey step, and the system that performs it."""

    number: str
    name: str
    system_id: str | None = None
    system_name: str | None = None

    def __post_init__(self) -> None:
        _text(self.number, "activity number")
        _text(self.name, "activity name")
        if (self.system_id is None) != (self.system_name is None):
            raise InvalidArchitectureContentError("An activity's system needs its name.")


@dataclass(frozen=True)
class JourneyStep:
    """A journey activity a mapped system performs or supports (ADR-0097).

    With the activities that lead into it and follow it, so a reviewer sees which
    systems hand over to and from the change. Advice, never mapped impact.
    """

    system_id: str
    journey_id: str
    journey_name: str
    number: str
    name: str
    performs: bool
    # The offering and order type the journey fulfils, by name, when it says.
    fulfils: tuple[str, ...] = ()
    before: tuple[JourneyNeighbour, ...] = ()
    after: tuple[JourneyNeighbour, ...] = ()

    def __post_init__(self) -> None:
        for field in ("system_id", "journey_id", "journey_name", "number", "name"):
            _text(getattr(self, field), field.replace("_", " "))


@dataclass(frozen=True)
class OrganisationReference:
    """A squad, value stream or product recorded as it was named at mapping time."""

    id: str
    name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "organisation id"))
        object.__setattr__(self, "name", _text(self.name, "organisation name"))


def _unique_ids(values: tuple[OrganisationReference, ...], label: str) -> None:
    ids = [item.id for item in values]
    if len(ids) != len(set(ids)):
        raise InvalidArchitectureContentError(f"System {label} must have unique ids.")


@dataclass(frozen=True)
class SystemReference:
    id: str
    name: str
    catalogued: bool
    capabilities: tuple[SystemCapability, ...] = ()
    constraints: tuple[str, ...] = ()
    squads: tuple[OrganisationReference, ...] = ()
    value_streams: tuple[OrganisationReference, ...] = ()
    products: tuple[OrganisationReference, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "system id"))
        object.__setattr__(self, "name", _text(self.name, "system name"))
        capability_ids = [item.id for item in self.capabilities]
        if len(capability_ids) != len(set(capability_ids)):
            raise InvalidArchitectureContentError("System capabilities must have unique ids.")
        _unique_ids(self.squads, "squads")
        _unique_ids(self.value_streams, "value streams")
        _unique_ids(self.products, "products")
        if any(not constraint.strip() for constraint in self.constraints):
            raise InvalidArchitectureContentError("Architecture constraints must not be blank.")


@dataclass(frozen=True)
class ArchitectureDependency:
    source_system_id: str
    target_system_id: str
    description: str
    kind: RelationshipKind = RelationshipKind.UNSPECIFIED

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "kind", relationship_kind(self.kind))
        except InvalidRelationshipKindError as exc:
            raise InvalidArchitectureContentError(str(exc)) from exc
        object.__setattr__(self, "source_system_id", _text(self.source_system_id, "source id"))
        object.__setattr__(self, "target_system_id", _text(self.target_system_id, "target id"))
        object.__setattr__(self, "description", _text(self.description, "dependency description"))
        if self.source_system_id == self.target_system_id:
            raise InvalidArchitectureContentError("A system cannot depend on itself.")

    def digest_fields(self) -> list[str]:
        """What approval and review fingerprints record.

        The kind joins only once it is specified, so dependencies recorded before
        kinds existed keep the fingerprints their approvals were given against.
        """
        fields = [self.source_system_id, self.target_system_id, self.description]
        if self.kind is not RelationshipKind.UNSPECIFIED:
            fields.append(self.kind.value)
        return fields


@dataclass(frozen=True)
class ArchitectureCitation:
    system_id: str
    chunk_id: str
    quote: str

    def __post_init__(self) -> None:
        for field in ("system_id", "chunk_id", "quote"):
            _text(getattr(self, field), field)
