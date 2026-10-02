"""AI-proposed catalogue changes that a maintainer accepts, edits or rejects.

A candidate never changes a release on its own. It records what a document
appears to say, where it says it, and which model said so; only a
maintainer's decision applies it to a draft. This keeps the rule that AI
evidence cannot create catalogue systems by itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from smb_requirement_agent.domain.architecture.journeys import Journey, same_journey
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    InvalidKnowledgeError,
    KnowledgeCapability,
    LandscapeDomain,
    RelationshipKind,
    SystemComponent,
    SystemDefinition,
    SystemRelationship,
    relationship_kind,
)
from smb_requirement_agent.domain.architecture.products import (
    ProductOffering,
    find_offering,
    find_offering_component,
    find_order_type,
    same_offering,
)


class CandidateKind(StrEnum):
    SYSTEM = "system"
    COMPONENT = "component"
    CAPABILITY = "capability"
    CONSTRAINT = "constraint"
    RELATIONSHIP = "relationship"
    # Where systems sit (ADR-0094): an area or sub-domain, and one system placed in one.
    LANDSCAPE_DOMAIN = "landscape_domain"
    PLACEMENT = "placement"
    # A whole product offering, reviewed as one (ADR-0095).
    PRODUCT = "product"
    # A whole journey: its activities, rules and integrations, reviewed as one (ADR-0096).
    JOURNEY = "journey"


class CandidateStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class CandidateMatch(StrEnum):
    """How a candidate relates to the draft as it stands now."""

    NEW = "new"
    UPDATES_EXISTING = "updates_existing"
    ALREADY_PRESENT = "already_present"
    NEEDS_SYSTEM = "needs_system"
    # A capability that names a component its system does not have yet.
    NEEDS_COMPONENT = "needs_component"
    # A placement, or a sub-domain, whose landscape domain the draft does not have yet.
    NEEDS_DOMAIN = "needs_domain"
    # A journey whose product offering, or that offering's order type, the draft does not have.
    NEEDS_OFFERING = "needs_offering"


class CandidateBasis(StrEnum):
    """Whether the document says this outright or the model read it from what it describes."""

    STATED = "stated"
    INFERRED = "inferred"


class MatchRole(StrEnum):
    """Which system reference of a candidate a possible match is for."""

    SYSTEM = "system"
    TARGET = "target"


class CandidateNotFoundError(Exception):
    """No such catalogue candidate for this release."""


class CandidateDecisionConflictError(Exception):
    """The candidate was already decided, or its draft moved on."""


class CandidateDependencyError(Exception):
    """The candidate refers to a system the draft does not contain yet."""


def _required(value: str, label: str) -> str:
    result = value.strip()
    if not result:
        raise InvalidKnowledgeError(f"{label} must not be blank.")
    return result


_DESCRIBED = frozenset(
    {CandidateKind.SYSTEM, CandidateKind.COMPONENT, CandidateKind.LANDSCAPE_DOMAIN}
)
_PLACING = frozenset({CandidateKind.LANDSCAPE_DOMAIN, CandidateKind.PLACEMENT})
# Reviewed and accepted whole, replacing the item they match; they name no one system.
_WHOLE = frozenset({CandidateKind.PRODUCT, CandidateKind.JOURNEY})


@dataclass(frozen=True)
class CandidateContent:
    """The proposed change. Which fields matter depends on the candidate kind.

    - system: ``system_id``, ``name``, optional ``name_ar``, ``aliases`` and
      ``description`` (what the system is for)
    - component: ``system_id``, ``component_id``, ``name``, optional ``name_ar``,
      ``aliases``, ``description`` and ``technology``
    - capability: ``system_id``, ``capability_id``, ``name``, ``triggers``, and
      ``component_id`` when the source says which component delivers it
    - constraint: ``system_id``, ``text``
    - relationship: ``system_id`` (source), ``target_system_id``, ``text``, and
      ``relationship_kind`` when the source says how the systems interact
    - landscape_domain: ``landscape_domain_id`` (also its ``system_id``, the
      suggestion's subject), ``name``, optional ``parent_domain_id``, ``name_ar``
      and ``description``
    - placement: ``system_id`` and the ``landscape_domain_id`` it sits in
    - product: the whole ``product`` offering; its id is also the ``system_id``,
      the suggestion's subject
    - journey: the whole ``journey``; its id is also the ``system_id``
    """

    kind: CandidateKind
    system_id: str
    name: str = ""
    name_ar: str | None = None
    aliases: tuple[str, ...] = ()
    capability_id: str | None = None
    triggers: tuple[str, ...] = ()
    target_system_id: str | None = None
    text: str = ""
    relationship_kind: RelationshipKind | None = None
    component_id: str | None = None
    description: str | None = None
    technology: str | None = None
    landscape_domain_id: str | None = None
    parent_domain_id: str | None = None
    product: ProductOffering | None = None
    journey: Journey | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", CandidateKind(self.kind))
        if self.relationship_kind is not None:
            if self.kind is not CandidateKind.RELATIONSHIP:
                raise InvalidKnowledgeError("Only a dependency has a relationship kind.")
            object.__setattr__(self, "relationship_kind", relationship_kind(self.relationship_kind))
        object.__setattr__(self, "system_id", _required(self.system_id, "System id"))
        object.__setattr__(self, "aliases", tuple(item.strip() for item in self.aliases))
        object.__setattr__(self, "triggers", tuple(item.strip() for item in self.triggers))
        if any(not item for item in (*self.aliases, *self.triggers)):
            raise InvalidKnowledgeError("Aliases and matching phrases must not be blank.")
        if self.component_id is not None:
            if self.kind not in {CandidateKind.COMPONENT, CandidateKind.CAPABILITY}:
                raise InvalidKnowledgeError("Only a component or a capability names a component.")
            object.__setattr__(self, "component_id", _required(self.component_id, "Component"))
        if self.technology is not None and self.kind is not CandidateKind.COMPONENT:
            raise InvalidKnowledgeError("Only a component has a technology.")
        if self.description is not None and self.kind not in _DESCRIBED:
            raise InvalidKnowledgeError("Only a system, component or domain has a description.")
        if self.landscape_domain_id is not None and self.kind not in _PLACING:
            raise InvalidKnowledgeError("Only a landscape domain or a placement names a domain.")
        if self.parent_domain_id is not None and self.kind is not CandidateKind.LANDSCAPE_DOMAIN:
            raise InvalidKnowledgeError("Only a landscape domain has a parent domain.")
        for field, label in (
            ("description", "Description"),
            ("technology", "Technology"),
            ("landscape_domain_id", "Landscape domain"),
            ("parent_domain_id", "Parent domain"),
        ):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, _required(value, label))
        if (self.product is not None) != (self.kind is CandidateKind.PRODUCT):
            raise InvalidKnowledgeError("Only a product offering suggestion holds an offering.")
        if (self.journey is not None) != (self.kind is CandidateKind.JOURNEY):
            raise InvalidKnowledgeError("Only a journey suggestion holds a journey.")
        if self.kind in _PLACING:
            _required(self.landscape_domain_id or "", "Landscape domain")
        if self.kind is CandidateKind.LANDSCAPE_DOMAIN:
            _required(self.name, "Landscape domain name")
            if self.parent_domain_id == self.landscape_domain_id:
                raise InvalidKnowledgeError("A landscape domain cannot be its own parent.")
        elif self.kind in _WHOLE or self.kind is CandidateKind.PLACEMENT:
            pass
        elif self.kind is CandidateKind.SYSTEM:
            _required(self.name, "System name")
        elif self.kind is CandidateKind.COMPONENT:
            _required(self.component_id or "", "Component id")
            _required(self.name, "Component name")
        elif self.kind is CandidateKind.CAPABILITY:
            _required(self.capability_id or "", "Capability id")
            _required(self.name, "Capability name")
            if not self.triggers:
                raise InvalidKnowledgeError("A capability needs non-empty matching phrases.")
        elif self.kind is CandidateKind.CONSTRAINT:
            _required(self.text, "Constraint")
        else:
            _required(self.target_system_id or "", "Relationship target")
            _required(self.text, "Relationship description")


@dataclass(frozen=True)
class CandidateCitation:
    location: str
    quote: str

    def __post_init__(self) -> None:
        _required(self.location, "Citation location")
        _required(self.quote, "Citation quote")


@dataclass(frozen=True)
class PossibleMatch:
    """An existing system that a name the document uses may refer to; a person confirms it."""

    role: MatchRole
    written_as: str
    system_id: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", MatchRole(self.role))
        _required(self.written_as, "Matched name")
        _required(self.system_id, "Matched system")
        _required(self.reason, "Match reason")


@dataclass(frozen=True)
class CatalogueCandidate:
    id: str
    release_id: str
    document_version_id: str
    content: CandidateContent
    citations: tuple[CandidateCitation, ...]
    model: str
    prompt_version: str
    created_at: datetime
    status: CandidateStatus = CandidateStatus.PROPOSED
    edited: bool = False
    decided_by: str | None = None
    decided_at: datetime | None = None
    basis: CandidateBasis = CandidateBasis.STATED
    rationale: str | None = None
    possible_matches: tuple[PossibleMatch, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", CandidateStatus(self.status))
        object.__setattr__(self, "basis", CandidateBasis(self.basis))
        if not self.citations:
            raise InvalidKnowledgeError("A catalogue candidate must cite its source.")
        if (self.status is CandidateStatus.PROPOSED) != (self.decided_at is None):
            raise InvalidKnowledgeError("Only decided candidates carry a decision time.")
        if self.basis is CandidateBasis.INFERRED:
            if self.content.kind is not CandidateKind.RELATIONSHIP:
                raise InvalidKnowledgeError("Only a dependency can be inferred.")
            _required(self.rationale or "", "Inference rationale")
        elif self.rationale is not None:
            raise InvalidKnowledgeError("Only an inferred suggestion carries a rationale.")

    def decide(
        self,
        accept: bool,
        actor_id: str,
        at: datetime,
        content: CandidateContent | None = None,
    ) -> CatalogueCandidate:
        if self.status is not CandidateStatus.PROPOSED:
            raise CandidateDecisionConflictError("This suggestion was already decided.")
        edited = content is not None and content != self.content
        if content is not None and content.kind is not self.content.kind:
            raise InvalidKnowledgeError("An edit cannot change what kind of item is suggested.")
        return replace(
            self,
            content=content if content is not None and accept else self.content,
            status=CandidateStatus.ACCEPTED if accept else CandidateStatus.REJECTED,
            edited=edited and accept,
            decided_by=actor_id,
            decided_at=at,
        )


def _labels(system: SystemDefinition) -> tuple[str, ...]:
    return tuple(
        label for label in (system.id, system.name, system.name_ar or "", *system.aliases) if label
    )


def _words(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def find_system(release: ArchitectureKnowledge, reference: str) -> SystemDefinition | None:
    """A draft system named by id, name, Arabic name or alias, ignoring case.

    Failing an exact label, the words alone are compared, so ``dynamics-crm``
    (the id of a suggested system) finds the system that has since taken
    "Dynamics CRM" as an alias; failing that, the words run together, so
    "CRM GW" finds "CRMGW". Each fallback answers only when one system fits.
    """
    key = reference.strip().casefold()
    exact = next(
        (
            system
            for system in release.systems
            if key in {label.casefold() for label in _labels(system)}
        ),
        None,
    )
    words = _words(reference)
    if exact is not None or not words:
        return exact
    loose = [
        system
        for system in release.systems
        if words in {_words(label) for label in _labels(system)}
    ]
    if loose:
        return loose[0] if len(loose) == 1 else None
    # Then with the spaces gone too, so "CRM GW" finds the system called "CRMGW".
    compact = words.replace(" ", "")
    joined = [
        system
        for system in release.systems
        if compact in {_words(label).replace(" ", "") for label in _labels(system)}
    ]
    return joined[0] if len(joined) == 1 else None


def find_landscape_domain(release: ArchitectureKnowledge, reference: str) -> LandscapeDomain | None:
    """A landscape domain named by id or, when only one has it, by name, ignoring case."""
    key = reference.strip().casefold()
    exact = next((item for item in release.landscape_domains if item.id.casefold() == key), None)
    if exact is not None or not key:
        return exact
    named = [
        item
        for item in release.landscape_domains
        if _words(item.name) == _words(reference) or _words(item.id) == _words(reference)
    ]
    return named[0] if len(named) == 1 else None


def _suggested_domain(
    content: CandidateContent, release: ArchitectureKnowledge
) -> LandscapeDomain | None:
    """The draft's domain a landscape-domain suggestion is: the same id, or the same name
    under the same parent."""
    same = find_landscape_domain(release, content.landscape_domain_id or "")
    if same is not None and same.id == content.landscape_domain_id:
        return same
    parent = (
        find_landscape_domain(release, content.parent_domain_id)
        if content.parent_domain_id
        else None
    )
    return next(
        (
            item
            for item in release.landscape_domains
            if (item.parent_id or None) == (parent.id if parent else None)
            and _words(item.name) == _words(content.name)
        ),
        None,
    )


def find_component(system: SystemDefinition, reference: str) -> SystemComponent | None:
    """A component of this system named by id, name, Arabic name or alias, ignoring case.

    As with systems, the words alone are compared when no label matches exactly,
    and that fallback answers only when one component fits.
    """
    key = reference.strip().casefold()
    exact = next(
        (
            component
            for component in system.components
            if key in {label.casefold() for label in (component.id, *component.labels)}
        ),
        None,
    )
    words = _words(reference)
    if exact is not None or not words:
        return exact
    loose = [
        component
        for component in system.components
        if words in {_words(label) for label in (component.id, *component.labels)}
    ]
    return loose[0] if len(loose) == 1 else None


def _component_of(content: CandidateContent, system: SystemDefinition) -> SystemComponent | None:
    return find_component(system, content.component_id or "") or find_component(
        system, content.name
    )


@dataclass(frozen=True)
class _ComponentAdditions:
    """What a suggestion adds to a component: labels no other component has, and empty fields."""

    aliases: tuple[str, ...]
    name_ar: str | None
    description: str | None
    technology: str | None

    @property
    def empty(self) -> bool:
        return not (self.aliases or self.name_ar or self.description or self.technology)


def _component_additions(
    content: CandidateContent, system: SystemDefinition, component: SystemComponent
) -> _ComponentAdditions:
    taken = {
        label.casefold()
        for item in system.components
        if item.id != component.id
        for label in item.labels
    }
    own = {label.casefold() for label in component.labels}
    name_ar = None
    if component.name_ar is None and content.name_ar:
        if content.name_ar.casefold() not in taken | own:
            name_ar = content.name_ar.strip()
    aliases = tuple(
        label
        for label in _merged((), (content.name.strip(), *content.aliases))
        if label.casefold() not in own | taken | {(name_ar or "").casefold()}
    )
    return _ComponentAdditions(
        aliases,
        name_ar,
        content.description if component.description is None else None,
        content.technology if component.technology is None else None,
    )


def _current_offering(
    offering: ProductOffering, release: ArchitectureKnowledge
) -> ProductOffering | None:
    return next((item for item in release.products if same_offering(item, offering)), None)


def _resolved_offering(
    offering: ProductOffering, release: ArchitectureKnowledge
) -> tuple[ProductOffering, tuple[str, ...]]:
    """The offering naming draft systems by their ids, and the names no draft system has."""
    missing: list[str] = []

    def resolved(reference: str) -> str:
        system = find_system(release, reference)
        if system is None:
            missing.append(reference)
            return reference
        return system.id

    components = tuple(
        replace(
            part,
            responsibilities=tuple(
                replace(duty, system_id=resolved(duty.system_id)) for duty in part.responsibilities
            ),
        )
        for part in offering.components
    )
    return replace(offering, components=components), tuple(dict.fromkeys(missing))


@dataclass(frozen=True)
class _JourneyGaps:
    """What a journey names that the draft does not have yet, as written."""

    systems: tuple[str, ...] = ()
    # The offering, or the order type that offering lacks.
    offering: str | None = None
    components: tuple[str, ...] = ()


def _current_journey(journey: Journey, release: ArchitectureKnowledge) -> Journey | None:
    return next((item for item in release.journeys if same_journey(item, journey)), None)


def _resolved_journey(
    journey: Journey, release: ArchitectureKnowledge
) -> tuple[Journey, _JourneyGaps]:
    """The journey naming the draft's systems, offering, order type and components by
    their ids, and what it names that the draft does not have."""
    systems: list[str] = []
    parts: list[str] = []

    def system(reference: str) -> str:
        found = find_system(release, reference)
        if found is None:
            systems.append(reference)
            return reference
        return found.id

    offering = find_offering(release.products, journey.product_id or "")
    gap = journey.product_id if journey.product_id and offering is None else None
    order = journey.order_type_code
    if offering is not None and order is not None:
        kind = find_order_type(offering, order)
        if kind is None:
            gap = f"{offering.name} › {order}"
        else:
            order = kind.code

    def component(reference: str) -> str:
        found = find_offering_component(offering, reference) if offering is not None else None
        if found is None:
            parts.append(reference)
            return reference
        return found.id

    activities = tuple(
        replace(
            item,
            performing_system_id=(
                system(item.performing_system_id) if item.performing_system_id else None
            ),
            supporting_system_ids=tuple(
                dict.fromkeys(system(name) for name in item.supporting_system_ids)
            ),
            component_ids=tuple(dict.fromkeys(component(name) for name in item.component_ids)),
        )
        for item in journey.activities
    )
    resolved = replace(
        journey,
        product_id=offering.id if offering is not None else journey.product_id,
        order_type_code=order,
        activities=activities,
    )
    return resolved, _JourneyGaps(tuple(dict.fromkeys(systems)), gap, tuple(dict.fromkeys(parts)))


def classify(content: CandidateContent, release: ArchitectureKnowledge) -> CandidateMatch:
    if content.kind is CandidateKind.JOURNEY and content.journey is not None:
        journey, gaps = _resolved_journey(content.journey, release)
        if gaps.systems:
            return CandidateMatch.NEEDS_SYSTEM
        if gaps.offering:
            return CandidateMatch.NEEDS_OFFERING
        if gaps.components:
            return CandidateMatch.NEEDS_COMPONENT
        kept = _current_journey(journey, release)
        if kept is None:
            return CandidateMatch.NEW
        same = replace(journey, id=kept.id) == kept
        return CandidateMatch.ALREADY_PRESENT if same else CandidateMatch.UPDATES_EXISTING
    if content.kind is CandidateKind.PRODUCT and content.product is not None:
        offering, missing = _resolved_offering(content.product, release)
        if missing:
            return CandidateMatch.NEEDS_SYSTEM
        existing = _current_offering(offering, release)
        if existing is None:
            return CandidateMatch.NEW
        same = replace(offering, id=existing.id) == existing
        return CandidateMatch.ALREADY_PRESENT if same else CandidateMatch.UPDATES_EXISTING
    if content.kind is CandidateKind.LANDSCAPE_DOMAIN:
        domain = _suggested_domain(content, release)
        if domain is None:
            parent = content.parent_domain_id
            if parent and find_landscape_domain(release, parent) is None:
                return CandidateMatch.NEEDS_DOMAIN
            return CandidateMatch.NEW
        fills = (content.description and not domain.description) or (
            content.name_ar and not domain.name_ar
        )
        return CandidateMatch.UPDATES_EXISTING if fills else CandidateMatch.ALREADY_PRESENT
    system = find_system(release, content.system_id)
    if content.kind is CandidateKind.SYSTEM:
        system = system or find_system(release, content.name)
        if system is None:
            return CandidateMatch.NEW
        known = {label.casefold() for label in (system.name, *system.aliases)}
        wanted = {
            label.casefold()
            for label in _free(release, (content.name, *content.aliases), system.id)
        }
        describes = content.description is not None and system.description is None
        return (
            CandidateMatch.ALREADY_PRESENT
            if wanted <= known and not describes
            else CandidateMatch.UPDATES_EXISTING
        )
    if system is None:
        return CandidateMatch.NEEDS_SYSTEM
    if content.kind is CandidateKind.PLACEMENT:
        place = find_landscape_domain(release, content.landscape_domain_id or "")
        if place is None:
            return CandidateMatch.NEEDS_DOMAIN
        if system.landscape_domain_id is None:
            return CandidateMatch.NEW
        return (
            CandidateMatch.ALREADY_PRESENT
            if system.landscape_domain_id == place.id
            else CandidateMatch.UPDATES_EXISTING
        )
    if content.kind is CandidateKind.COMPONENT:
        component = _component_of(content, system)
        if component is None:
            return CandidateMatch.NEW
        return (
            CandidateMatch.ALREADY_PRESENT
            if _component_additions(content, system, component).empty
            else CandidateMatch.UPDATES_EXISTING
        )
    if content.kind is CandidateKind.CAPABILITY:
        named = None
        if content.component_id is not None:
            named = find_component(system, content.component_id)
            if named is None:
                return CandidateMatch.NEEDS_COMPONENT
        current = next(
            (item for item in system.capabilities if item.id == content.capability_id), None
        )
        if current is None:
            return CandidateMatch.NEW
        places = named is not None and current.component_id is None
        return (
            CandidateMatch.ALREADY_PRESENT
            if set(content.triggers) <= set(current.triggers)
            and current.name == content.name
            and not places
            else CandidateMatch.UPDATES_EXISTING
        )
    if content.kind is CandidateKind.CONSTRAINT:
        present = content.text.casefold() in {item.casefold() for item in system.constraints}
        return CandidateMatch.ALREADY_PRESENT if present else CandidateMatch.NEW
    target = find_system(release, content.target_system_id or "")
    if target is None:
        return CandidateMatch.NEEDS_SYSTEM
    link = _relationship(release, system.id, target.id, content.text)
    if link is None:
        return CandidateMatch.NEW
    return (
        CandidateMatch.UPDATES_EXISTING
        if _new_kind(content, link) is not None
        else CandidateMatch.ALREADY_PRESENT
    )


def _relationship(
    release: ArchitectureKnowledge, source_id: str, target_id: str, text: str
) -> SystemRelationship | None:
    return next(
        (
            item
            for item in release.relationships
            if item.source_system_id == source_id
            and item.target_system_id == target_id
            and item.description.casefold() == text.casefold()
        ),
        None,
    )


def _new_kind(content: CandidateContent, current: SystemRelationship) -> RelationshipKind | None:
    """The kind a suggestion would set: only a stated kind that differs from the record."""
    wanted = content.relationship_kind
    if wanted is None or wanted is RelationshipKind.UNSPECIFIED or wanted is current.kind:
        return None
    return wanted


def open_matches(
    candidate: CatalogueCandidate, release: ArchitectureKnowledge
) -> tuple[PossibleMatch, ...]:
    """The possible matches still to decide: those whose name no draft system answers to yet."""
    content = candidate.content
    if content.kind is CandidateKind.LANDSCAPE_DOMAIN or content.kind in _WHOLE:
        return ()
    if content.kind is CandidateKind.SYSTEM:
        still_new = classify(content, release) is CandidateMatch.NEW
        return candidate.possible_matches if still_new else ()
    references = {
        MatchRole.SYSTEM: content.system_id,
        MatchRole.TARGET: content.target_system_id or "",
    }
    return tuple(
        match
        for match in candidate.possible_matches
        if find_system(release, references[match.role]) is None
    )


def needs_one_by_one(candidate: CatalogueCandidate, release: ArchitectureKnowledge) -> bool:
    """Inferred, perhaps an existing system, or moving a placed system: never accepted in bulk."""
    # Moving a placed system, or replacing an offering or journey, changes what a person chose.
    moves = (
        candidate.content.kind is CandidateKind.PLACEMENT or candidate.content.kind in _WHOLE
    ) and classify(candidate.content, release) is CandidateMatch.UPDATES_EXISTING
    return (
        candidate.basis is CandidateBasis.INFERRED
        or moves
        or bool(open_matches(candidate, release))
    )


def _free(
    release: ArchitectureKnowledge, labels: tuple[str, ...], owner_id: str
) -> tuple[str, ...]:
    """The labels that do not already name another system.

    Each name and alias must identify one system, so a suggestion never takes a
    label from the system that already has it; the rest of it still applies.
    """
    return tuple(
        label
        for label in labels
        if (found := find_system(release, label)) is None or found.id == owner_id
    )


def _merged(values: tuple[str, ...], additions: tuple[str, ...]) -> tuple[str, ...]:
    seen = {value.casefold() for value in values}
    extra = []
    for value in additions:
        if value.casefold() not in seen:
            seen.add(value.casefold())
            extra.append(value)
    return (*values, *extra)


def _require_system(release: ArchitectureKnowledge, reference: str) -> SystemDefinition:
    system = find_system(release, reference)
    if system is None:
        raise CandidateDependencyError(
            f"Accept or add system {reference!r} before items that belong to it."
        )
    return system


def _with_system(release: ArchitectureKnowledge, system: SystemDefinition) -> ArchitectureKnowledge:
    systems = tuple(system if item.id == system.id else item for item in release.systems)
    if not any(item.id == system.id for item in release.systems):
        systems = (*systems, system)
    return release.updated(systems=systems)


def _with_component(content: CandidateContent, system: SystemDefinition) -> SystemDefinition:
    """The system with a suggested component added, or merged into the one it names."""
    current = _component_of(content, system)
    if current is None:
        current = SystemComponent(id=content.component_id or "", name=content.name.strip())
        components = (*system.components, current)
    else:
        components = system.components
    additions = _component_additions(content, system, current)
    merged = replace(
        current,
        aliases=_merged(current.aliases, additions.aliases),
        name_ar=current.name_ar or additions.name_ar,
        description=current.description or additions.description,
        technology=current.technology or additions.technology,
    )
    return replace(
        system,
        components=tuple(merged if item.id == merged.id else item for item in components),
    )


def _with_domain(
    content: CandidateContent, release: ArchitectureKnowledge
) -> ArchitectureKnowledge:
    """The draft with a suggested landscape domain added, or its gaps filled."""
    current = _suggested_domain(content, release)
    if current is not None:
        filled = replace(
            current,
            name_ar=current.name_ar or content.name_ar,
            description=current.description or content.description,
        )
        return release.updated(
            landscape_domains=tuple(
                filled if item.id == current.id else item for item in release.landscape_domains
            )
        )
    parent = None
    if content.parent_domain_id:
        parent = find_landscape_domain(release, content.parent_domain_id)
        if parent is None:
            raise CandidateDependencyError(
                f"Accept or add landscape domain {content.parent_domain_id!r} before the "
                "domains inside it."
            )
    domain = LandscapeDomain(
        content.landscape_domain_id or "",
        content.name.strip(),
        content.name_ar,
        parent.id if parent else None,
        content.description,
    )
    return release.updated(landscape_domains=(*release.landscape_domains, domain))


def _with_offering(
    offering: ProductOffering, release: ArchitectureKnowledge
) -> ArchitectureKnowledge:
    resolved, missing = _resolved_offering(offering, release)
    if missing:
        raise CandidateDependencyError(
            f"Accept or add {', '.join(repr(item) for item in missing)} before the product "
            f"offering {offering.name} that names them."
        )
    current = _current_offering(resolved, release)
    if current is None:
        return release.updated(products=(*release.products, resolved))
    kept = replace(resolved, id=current.id)
    return release.updated(
        products=tuple(kept if item.id == current.id else item for item in release.products)
    )


def _with_journey(journey: Journey, release: ArchitectureKnowledge) -> ArchitectureKnowledge:
    resolved, gaps = _resolved_journey(journey, release)
    missing = (
        [repr(item) for item in gaps.systems]
        + ([f"product offering {gaps.offering!r}"] if gaps.offering else [])
        + [f"component {item!r}" for item in gaps.components]
    )
    if missing:
        raise CandidateDependencyError(
            f"Accept or add {', '.join(missing)} before the journey {journey.name} that names "
            "them, or edit the journey."
        )
    current = _current_journey(resolved, release)
    if current is None:
        return release.updated(journeys=(*release.journeys, resolved))
    kept = replace(resolved, id=current.id)
    return release.updated(
        journeys=tuple(kept if item.id == current.id else item for item in release.journeys)
    )


def apply_candidate(
    content: CandidateContent, release: ArchitectureKnowledge
) -> ArchitectureKnowledge:
    """The draft with this change merged in; existing information is kept, never dropped.

    A product offering or a journey is the exception: accepting one replaces the
    one it matches, as a whole, because it was reviewed as a whole.
    """
    if content.kind is CandidateKind.PRODUCT and content.product is not None:
        return _with_offering(content.product, release)
    if content.kind is CandidateKind.JOURNEY and content.journey is not None:
        return _with_journey(content.journey, release)
    if content.kind is CandidateKind.LANDSCAPE_DOMAIN:
        return _with_domain(content, release)
    if content.kind is CandidateKind.SYSTEM:
        existing = find_system(release, content.system_id) or find_system(release, content.name)
        arabic = (content.name_ar,) if content.name_ar else ()
        if existing is None:
            name = content.name.strip()
            name_ar = next(iter(_free(release, arabic, content.system_id)), None)
            return _with_system(
                release,
                SystemDefinition(
                    id=content.system_id,
                    name=name,
                    aliases=tuple(
                        label
                        for label in _merged((), _free(release, content.aliases, content.system_id))
                        if label.casefold() not in {name.casefold(), (name_ar or "").casefold()}
                    ),
                    name_ar=name_ar,
                    description=content.description,
                ),
            )
        taken = {
            existing.name.casefold(),
            existing.id.casefold(),
            (existing.name_ar or "").casefold(),
        }
        extra = tuple(
            label
            for label in _free(release, (content.name.strip(), *content.aliases), existing.id)
            if label.casefold() not in taken
        )
        aliases = _merged(existing.aliases, extra)
        name_ar = existing.name_ar or next(
            (
                label
                for label in _free(release, arabic, existing.id)
                if label.casefold() not in {alias.casefold() for alias in aliases}
            ),
            None,
        )
        return _with_system(
            release,
            replace(
                existing,
                aliases=aliases,
                name_ar=name_ar,
                # A suggestion fills a missing description; it never replaces one.
                description=existing.description or content.description,
            ),
        )
    system = _require_system(release, content.system_id)
    if content.kind is CandidateKind.PLACEMENT:
        place = find_landscape_domain(release, content.landscape_domain_id or "")
        if place is None:
            raise CandidateDependencyError(
                f"Accept or add landscape domain {content.landscape_domain_id!r} before placing "
                "systems in it."
            )
        return _with_system(release, replace(system, landscape_domain_id=place.id))
    if content.kind is CandidateKind.COMPONENT:
        return _with_system(release, _with_component(content, system))
    if content.kind is CandidateKind.CAPABILITY:
        capability_id = content.capability_id or ""
        current = next((item for item in system.capabilities if item.id == capability_id), None)
        named = None
        if content.component_id is not None:
            named = find_component(system, content.component_id)
            if named is None:
                raise CandidateDependencyError(
                    f"Accept or add component {content.component_id!r} of {system.name} before "
                    "the capabilities it delivers."
                )
        capability = KnowledgeCapability(
            capability_id,
            content.name.strip(),
            _merged(current.triggers, content.triggers) if current else content.triggers,
            # A suggestion never moves a capability out of the domain it was placed in,
            current.domain_id if current else None,
            # nor out of its component; it only places one that has none.
            (current.component_id if current else None) or (named.id if named else None),
        )
        capabilities = (
            tuple(capability if item.id == capability_id else item for item in system.capabilities)
            if current
            else (*system.capabilities, capability)
        )
        return _with_system(release, replace(system, capabilities=capabilities))
    if content.kind is CandidateKind.CONSTRAINT:
        return _with_system(
            release,
            replace(system, constraints=_merged(system.constraints, (content.text.strip(),))),
        )
    target = _require_system(release, content.target_system_id or "")
    link = _relationship(release, system.id, target.id, content.text)
    if link is not None:
        kind = _new_kind(content, link)
        if kind is None:
            return release.updated()
        return release.updated(
            relationships=tuple(
                replace(item, kind=kind) if item is link else item for item in release.relationships
            )
        )
    relationship = SystemRelationship(
        system.id,
        target.id,
        content.text.strip(),
        content.relationship_kind or RelationshipKind.UNSPECIFIED,
    )
    return release.updated(relationships=(*release.relationships, relationship))
