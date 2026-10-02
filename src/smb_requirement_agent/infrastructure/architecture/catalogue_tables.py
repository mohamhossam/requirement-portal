"""Catalogue tables read without a model: systems, offerings and journeys (ADR-0093).

A landscape document's tables already say exactly what the catalogue needs: a
system row names the system, its ID and aliases and the systems it integrates
with; an integration-details row links two activities whose performing systems
another table names. Reading those cells directly gives every row, cited by its
own line, the same way each time. The model still reads everything else, and the
system rows' Function cells for capabilities, which need wording.

Only rows that carry their cells are read here (Markdown tables, ADR-0090).
Nothing is decided: every result is a suggestion a maintainer reviews.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from smb_requirement_agent.application.ports.catalogue_extractor import (
    CatalogueExtractionError,
    CatalogueExtractorPort,
    CatalogueProposal,
    ExtractionRequest,
    ExtractionSegment,
    ProposedChange,
)
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateBasis,
    CandidateContent,
    CandidateKind,
)
from smb_requirement_agent.domain.architecture.journeys import (
    Activity,
    ActivityIntegration,
    FlowRule,
    Journey,
    flow_rule_kind,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    InvalidKnowledgeError,
    RelationshipKind,
)
from smb_requirement_agent.domain.architecture.products import (
    ComponentResponsibility,
    OfferingComponent,
    OfferingPoint,
    OrderType,
    ProductOffering,
    SourceConfidence,
    find_offering_component,
    find_order_type,
)
from smb_requirement_agent.infrastructure.llm.catalogue_extraction import plain_name, slug

READER = "catalogue-table-reader"
READER_VERSION = "catalogue-tables-v4"
# An Integrations entry longer than this is a phrase ("Same service context as
# B2B Web"), not the name of a system.
_MAX_ENTRY_WORDS = 4

# Column names as they are compared: lower case, words only ("Interface / API / event"
# reads "interface api event"); "#" is kept as a word.
_SYSTEM = frozenset({"system", "system name", "application"})
_ID = frozenset({"id", "system id"})
_FUNCTION = frozenset({"function", "purpose"})
_INTEGRATIONS = frozenset({"integrations", "integrates with", "interfaces"})
_ALIASES = frozenset({"aliases", "alias", "also known as", "other names"})
_EVIDENCE = frozenset({"evidence"})
_NUMBER = frozenset({"#", "no", "step"})
_ACTIVITY = frozenset({"activity"})
_PERFORMER = frozenset({"performing system", "performed by"})
_FROM = frozenset({"from"})
_TO = frozenset({"to"})
_INTERACTION = frozenset({"interaction", "interaction type"})
_INTERFACE = frozenset({"interface", "interface api event"})
_PAYLOAD = frozenset({"payload"})
_DOMAIN = frozenset({"domain", "domain name", "landscape domain"})
_CODE = frozenset({"code"})
_SUBDOMAIN = frozenset({"sub domain", "subdomain"})
_NOTHING = frozenset({"", "-", "—", "–"})
_VIA = re.compile(r"\s+via\s+", re.IGNORECASE)
_QUALIFIER = re.compile(r"\s*\([^()]*\)\s*$")


def _column(name: str) -> str:
    return " ".join(re.findall(r"[\w#]+", name.casefold()))


@dataclass(frozen=True)
class _Row:
    segment: ExtractionSegment
    values: dict[str, str]

    def get(self, names: frozenset[str]) -> str:
        return next((self.values[name] for name in sorted(names) if self.values.get(name)), "")

    @property
    def shape(self) -> str | None:
        columns = frozenset(self.values)
        if columns & _FROM and columns & _TO and columns & _INTERACTION:
            return "integration"
        if columns & _NUMBER and columns & _ACTIVITY and columns & _PERFORMER:
            return "activity"
        if columns & _SYSTEM and columns & (_ID | _FUNCTION | _INTEGRATIONS | _ALIASES):
            return "system"
        if columns & _DOMAIN and columns & (_ID | _CODE):
            return "domain"
        return None

    @property
    def basis(self) -> tuple[CandidateBasis, str | None]:
        if self.get(_EVIDENCE).upper() == "INFERRED":
            return CandidateBasis.INFERRED, "The document marks this row INFERRED."
        return CandidateBasis.STATED, None

    @property
    def gap(self) -> bool:
        return self.get(_EVIDENCE).upper() == "GAP"


def _row(segment: ExtractionSegment) -> _Row:
    values: dict[str, str] = {}
    for name, value in segment.cells:
        cleaned = value.strip()
        values.setdefault(_column(name), "" if cleaned in _NOTHING else cleaned)
    return _Row(segment, values)


def _entries(cell: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;]", cell) if item.strip()]


class _Names:
    """A document's names for its systems, and the catalogue's, as ids."""

    def __init__(self, request: ExtractionRequest) -> None:
        self._ids: dict[str, str] = {}
        # "ECM (catalog)" is written "ECM" elsewhere: a name without its trailing
        # parenthesis answers too, while only one system has that base (None after).
        self._bases: dict[str, str | None] = {}
        for system in request.known_systems:
            self.add(system.id, system.id, system.name, *system.aliases)

    def add(self, system_id: str, *labels: str) -> None:
        for label in labels:
            if label.strip():
                self._ids.setdefault(label.casefold().strip(), system_id)
                base = _QUALIFIER.sub("", label).casefold().strip()
                if base and base != label.casefold().strip():
                    owner = self._bases.setdefault(base, system_id)
                    if owner != system_id:
                        self._bases[base] = None

    def known(self, name: str) -> bool:
        return name.casefold().strip() in self._ids

    def resolve(self, name: str) -> str:
        key = name.casefold().strip()
        return self._ids.get(key) or self._bases.get(key) or slug(name)


class _Landscape:
    """The document's landscape domains, and each proposed once (ADR-0094)."""

    def __init__(self) -> None:
        self._by_key: dict[str, str] = {}
        self._codes: dict[str, str] = {}
        self.proposed: set[str] = set()

    def add(self, domain_id: str, name: str, code: str = "") -> None:
        for key in (domain_id, name):
            self._by_key.setdefault(key.casefold().strip(), domain_id)
        if code:
            self._codes.setdefault(code.casefold().strip(), domain_id)

    def find(self, reference: str) -> str | None:
        key = reference.casefold().strip()
        return self._by_key.get(key) or self._codes.get(key) or self._by_key.get(slug(reference))

    def heading(self, section: tuple[str, ...]) -> str | None:
        """The domain a table sits under: its heading is the domain's name, or "Name (Code)"."""
        for heading in reversed(section):
            base = _QUALIFIER.sub("", heading).strip()
            qualifier = heading[len(base) :].strip().strip("()").strip()
            found = self.find(base) or (self.find(qualifier) if qualifier else None)
            if found:
                return found
        return None


@dataclass
class TableReading:
    """What the tables gave, and which rows the model need not see, or need only partly."""

    changes: list[ProposedChange] = field(default_factory=list)
    # Rows the model has nothing left to read in.
    consumed: set[int] = field(default_factory=set)
    # Rows whose systems and dependencies were taken; the model reads the rest.
    read: set[int] = field(default_factory=set)
    # What could not be read, in words for the reading's notes.
    notes: list[str] = field(default_factory=list)


def _proposed(
    row: _Row, content: CandidateContent, source: str, target: str = ""
) -> ProposedChange:
    basis, rationale = row.basis
    return ProposedChange(
        content,
        (row.segment.location,),
        row.segment.text,
        source_name=source,
        target_name=target,
        basis=basis,
        rationale=rationale,
        reader=(READER, READER_VERSION),
    )


class CatalogueTableReader:
    def read(self, request: ExtractionRequest) -> TableReading:
        rows = [row for row in map(_row, request.segments) if row.values]
        names = _Names(request)
        reading = TableReading()
        landscape = _Landscape()
        for row in rows:
            if row.shape == "domain":
                reading.consumed.add(row.segment.number)
                if not row.gap:
                    reading.changes.extend(self._domain(row, landscape))
        systems: list[tuple[_Row, str, str]] = []
        for row in rows:
            name = plain_name(row.get(_SYSTEM)) if row.shape == "system" else ""
            if not name:
                continue
            reading.read.add(row.segment.number)
            if row.gap:
                continue
            system_id = names.resolve(name)
            aliases = [plain_name(item) for item in _entries(row.get(_ALIASES))]
            aliases.append(row.get(_ID))
            names.add(system_id, name, *aliases)
            systems.append((row, system_id, name))
            others = tuple(
                dict.fromkeys(
                    item for item in aliases if item and item.casefold() != name.casefold()
                )
            )
            content = CandidateContent(
                CandidateKind.SYSTEM,
                system_id,
                name=name,
                aliases=others,
                description=row.get(_FUNCTION) or None,
            )
            reading.changes.append(_proposed(row, content, name))
            reading.changes.extend(self._placement(row, system_id, name, landscape))
        # Integrations name systems that may appear in later rows, so they are read last.
        for row, system_id, name in systems:
            for entry in _entries(row.get(_INTEGRATIONS)):
                reading.changes.extend(self._integration(row, system_id, name, entry, names))
        performers = {
            row.get(_NUMBER): plain_name(row.get(_PERFORMER))
            for row in rows
            if row.shape == "activity" and row.get(_NUMBER) and row.get(_PERFORMER)
        }
        for row in rows:
            if row.shape == "integration":
                reading.consumed.add(row.segment.number)
                if not row.gap:
                    reading.changes.extend(self._activity_link(row, performers, names))
        offerings: dict[str, ProductOffering] = {}
        for section in _offering_sections(request.segments):
            offering = section.read_into(reading, names)
            if offering is not None:
                offerings[section.name.casefold()] = offering
        for journey in _journey_sections(request.segments):
            journey.read_into(reading, names, offerings.get((journey.product or "").casefold()))
        return reading

    def _domain(self, row: _Row, landscape: _Landscape) -> list[ProposedChange]:
        """A row of a Domains table: its ID is the domain's key, its code a description."""
        name = row.get(_DOMAIN)
        if not name:
            return []
        domain_id = slug(row.get(_ID) or name)
        code = row.get(_CODE)
        landscape.add(domain_id, name, code)
        landscape.proposed.add(domain_id)
        content = CandidateContent(
            CandidateKind.LANDSCAPE_DOMAIN,
            domain_id,
            name=name,
            landscape_domain_id=domain_id,
            description=code or None,
        )
        return [_proposed(row, content, name)]

    def _placement(
        self, row: _Row, system_id: str, name: str, landscape: _Landscape
    ) -> list[ProposedChange]:
        """Where a system row's system sits: a Domain cell, or the heading of its table,
        and below that its Sub-domain cell, proposed as a sub-domain the first time."""
        changes: list[ProposedChange] = []
        written = row.get(_DOMAIN)
        place = landscape.find(written) if written else landscape.heading(row.segment.section)
        if written and place is None:
            # A domain the Domains table did not list is still where the row says it is.
            place = slug(written)
            landscape.add(place, written)
            landscape.proposed.add(place)
            content = CandidateContent(
                CandidateKind.LANDSCAPE_DOMAIN, place, name=written, landscape_domain_id=place
            )
            changes.append(_proposed(row, content, written))
        if place is None:
            return changes
        sub = row.get(_SUBDOMAIN)
        if sub:
            child = f"{place}-{slug(sub)}"
            if child not in landscape.proposed:
                landscape.proposed.add(child)
                content = CandidateContent(
                    CandidateKind.LANDSCAPE_DOMAIN,
                    child,
                    name=sub,
                    landscape_domain_id=child,
                    parent_domain_id=place,
                )
                changes.append(_proposed(row, content, sub))
            place = child
        content = CandidateContent(CandidateKind.PLACEMENT, system_id, landscape_domain_id=place)
        changes.append(_proposed(row, content, name))
        return changes

    def _integration(
        self, row: _Row, system_id: str, name: str, entry: str, names: _Names
    ) -> list[ProposedChange]:
        """One Integrations entry as dependencies: "A / B" is two systems unless one is named so."""
        parts = _VIA.split(entry, maxsplit=1)
        written, qualifier = parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
        targets = (
            [written]
            if names.known(written) or "/" not in written
            else [part.strip() for part in written.split("/") if part.strip()]
        )
        changes: list[ProposedChange] = []
        for target in targets:
            target_id = names.resolve(target)
            if (
                len(target.split()) > _MAX_ENTRY_WORDS
                or target_id.casefold() == system_id.casefold()
            ):
                continue
            text = f"Integrates with {target}" + (f" via {qualifier}" if qualifier else "")
            content = CandidateContent(
                CandidateKind.RELATIONSHIP,
                system_id,
                target_system_id=target_id,
                text=text,
                relationship_kind=RelationshipKind.UNSPECIFIED,
            )
            changes.append(_proposed(row, content, name, target))
        return changes

    def _activity_link(
        self, row: _Row, performers: dict[str, str], names: _Names
    ) -> list[ProposedChange]:
        """An integration between two activities, as a dependency between their systems."""
        source, target = performers.get(row.get(_FROM)), performers.get(row.get(_TO))
        if not source or not target:
            return []
        source_id, target_id = names.resolve(source), names.resolve(target)
        if source_id.casefold() == target_id.casefold():
            return []
        interaction = row.get(_INTERACTION)
        details = ", ".join(item for item in (interaction, row.get(_INTERFACE)) if item)
        payload = row.get(_PAYLOAD)
        content = CandidateContent(
            CandidateKind.RELATIONSHIP,
            source_id,
            target_system_id=target_id,
            text=f"{payload} ({details})" if payload and details else payload or details,
            relationship_kind=(
                RelationshipKind.CALLS_API
                if interaction.casefold() == "api"
                else RelationshipKind.UNSPECIFIED
            ),
        )
        return [_proposed(row, content, source, target)]


# What the reader takes from a row it reads; the model's copies of these are duplicates.
_FROM_CELLS = frozenset(
    {
        CandidateKind.SYSTEM,
        CandidateKind.RELATIONSHIP,
        CandidateKind.LANDSCAPE_DOMAIN,
        CandidateKind.PLACEMENT,
        CandidateKind.PRODUCT,
        CandidateKind.JOURNEY,
    }
)


# Product offerings (ADR-0095) ---------------------------------------------------------------

_PRODUCT_HEADING = re.compile(r"^product\s*:\s*(?P<name>.+)$", re.IGNORECASE)
_RULES = re.compile(r"^\W*product rules\W*:?\W*", re.IGNORECASE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_FAMILY = frozenset({"family"})
_VERSION = frozenset({"version"})
_LIFECYCLE = frozenset({"lifecycle"})
_SOURCE = frozenset({"source"})
_ORDER_TYPE = frozenset({"order type"})
_ENABLED = frozenset({"enabled", "offered"})
_DESCRIPTION = frozenset({"description"})
_VALUE = frozenset({"value", "customer value"})
_AUDIENCE = frozenset({"fit", "audience", "segment", "who it is for"})
_COMPONENT = frozenset({"component"})
_KIND = frozenset({"type"})
_MANDATORY = frozenset({"mandatory"})
_VISIBLE = frozenset({"customer visible"})
_COMMERCIAL = frozenset({"commercial spec"})
_TECHNICAL = frozenset({"technical spec"})
_DETAILS = frozenset({"technical details"})
_ROLE = frozenset({"role"})
_RESPONSIBILITY = frozenset({"responsibility"})
_ORDER_TYPES = frozenset({"order types"})
_CONFIDENCE = {"CONFIRMED": "confirmed", "INFERRED": "inferred", "GAP": "gap"}


def _product_name(segment: ExtractionSegment) -> str | None:
    """The offering a segment belongs to: the nearest "Product: X" heading above it."""
    for heading in reversed(segment.section):
        if match := _PRODUCT_HEADING.match(plain_name(heading)):
            return match["name"].strip()
    return None


def _yes(value: str) -> bool | None:
    text = value.strip().casefold()
    return True if text in {"yes", "y", "true"} else False if text in {"no", "n", "false"} else None


def _trust(row: _Row) -> SourceConfidence | None:
    found = _CONFIDENCE.get(row.get(_EVIDENCE).upper())
    return SourceConfidence(found) if found else None


@dataclass
class _OfferingSection:
    """One "Product: X" section of a document, read into one offering suggestion."""

    name: str
    heading: ExtractionSegment | None = None
    segments: list[ExtractionSegment] = field(default_factory=list)

    def read_into(self, reading: TableReading, names: _Names) -> ProductOffering | None:
        facts: _Row | None = None
        orders: list[OrderType] = []
        parts: dict[str, OfferingComponent] = {}
        duties: list[tuple[str, ComponentResponsibility]] = []
        values: list[OfferingPoint] = []
        audiences: list[OfferingPoint] = []
        proposition: list[str] = []
        rules: list[str] = []
        order_keys: dict[str, str] = {}
        for segment in self.segments:
            if not segment.cells:
                text = segment.text.strip()
                if _RULES.match(text):
                    rules.extend(
                        item.strip()
                        for item in _SENTENCE.split(_RULES.sub("", text))
                        if item.strip()
                    )
                elif any("proposition" in heading.casefold() for heading in segment.section):
                    proposition.append(text)
                continue
            row = _row(segment)
            columns = frozenset(row.values)
            # An offering keeps a known gap as one, rather than leaving the row out.
            if columns & _COMPONENT and columns & _SYSTEM and columns & _ROLE:
                reading.read.add(segment.number)
                system = plain_name(row.get(_SYSTEM))
                delivered = row.get(_COMPONENT)
                if system and delivered and row.get(_ROLE):
                    duties.append(
                        (
                            delivered,
                            ComponentResponsibility(
                                names.resolve(system),
                                row.get(_ROLE),
                                row.get(_RESPONSIBILITY) or row.get(_DESCRIPTION) or delivered,
                                tuple(_entries(row.get(_ORDER_TYPES))),
                                _trust(row),
                                row.get(_SOURCE) or None,
                            ),
                        )
                    )
            elif columns & _COMPONENT and columns & (_KIND | _MANDATORY | _CODE):
                reading.read.add(segment.number)
                name = row.get(_COMPONENT)
                if name:
                    code = row.get(_CODE) or None
                    part_id = slug(code or name)
                    parts.setdefault(
                        part_id,
                        OfferingComponent(
                            part_id,
                            name,
                            code=code,
                            kind=row.get(_KIND) or None,
                            mandatory=_yes(row.get(_MANDATORY)),
                            customer_visible=_yes(row.get(_VISIBLE)),
                            description=row.get(_DESCRIPTION) or None,
                            commercial_spec=row.get(_COMMERCIAL) or None,
                            technical_spec=row.get(_TECHNICAL) or None,
                            technical_details=row.get(_DETAILS) or None,
                            confidence=_trust(row),
                            source=row.get(_SOURCE) or None,
                        ),
                    )
            elif columns & _ORDER_TYPE:
                reading.consumed.add(segment.number)
                name = row.get(_ORDER_TYPE)
                if name:
                    code = row.get(_CODE) or "_".join(name.upper().split())
                    order_keys[name.casefold()] = order_keys[code.casefold()] = code
                    orders.append(
                        OrderType(
                            code,
                            name,
                            _yes(row.get(_ENABLED)) is not False,
                            row.get(_DESCRIPTION) or None,
                            _trust(row),
                            row.get(_SOURCE) or None,
                        )
                    )
            elif columns & _VALUE or columns & _AUDIENCE:
                reading.consumed.add(segment.number)
                name = row.get(_VALUE) or row.get(_AUDIENCE)
                if name:
                    point = OfferingPoint(
                        name, row.get(_DESCRIPTION) or None, _trust(row), row.get(_SOURCE) or None
                    )
                    (values if columns & _VALUE else audiences).append(point)
            elif columns & _CODE and columns & (_FAMILY | _VERSION | _LIFECYCLE):
                reading.consumed.add(segment.number)
                facts = facts or row
        by_name = {part.name.casefold(): part_id for part_id, part in parts.items()}
        for written, duty in duties:
            part_id = by_name.get(written.casefold()) or slug(written)
            part = parts.get(part_id) or OfferingComponent(part_id, written)
            known = tuple(
                order_keys[item.casefold()]
                for item in duty.order_types
                if item.casefold() in order_keys
            )
            parts[part_id] = replace(
                part, responsibilities=(*part.responsibilities, replace(duty, order_types=known))
            )
        code = facts.get(_CODE) if facts else ""
        try:
            offering = ProductOffering(
                id=slug(code or self.name),
                name=self.name,
                code=code or None,
                family=(facts.get(_FAMILY) if facts else "") or None,
                version=(facts.get(_VERSION) if facts else "") or None,
                lifecycle=(facts.get(_LIFECYCLE) if facts else "") or None,
                proposition="\n\n".join(proposition) or None,
                rules=tuple(rules),
                order_types=tuple(orders),
                components=tuple(parts.values()),
                values=tuple(values),
                audiences=tuple(audiences),
                confidence=_trust(facts) if facts else None,
                source=(facts.get(_SOURCE) if facts else "") or None,
            )
        except InvalidKnowledgeError as exc:
            reading.notes.append(f"The product offering {self.name} could not be read: {exc}")
            return None
        if not (orders or parts or values or audiences or facts):
            return None
        cited = self.heading or (self.segments[0] if self.segments else None)
        if cited is None:
            return None
        reading.changes.append(
            ProposedChange(
                CandidateContent(
                    CandidateKind.PRODUCT, offering.id, name=offering.name, product=offering
                ),
                (cited.location,),
                cited.text,
                source_name=offering.name,
                reader=(READER, READER_VERSION),
            )
        )
        return offering


def _offering_sections(segments: tuple[ExtractionSegment, ...]) -> list[_OfferingSection]:
    sections: dict[str, _OfferingSection] = {}
    for segment in segments:
        heading = _PRODUCT_HEADING.match(plain_name(segment.text)) if not segment.cells else None
        name = _product_name(segment)
        if heading and name is None:
            # The heading itself sits above its section, so its own section does not name it.
            key = heading["name"].strip()
            sections.setdefault(key.casefold(), _OfferingSection(key)).heading = segment
            continue
        if name is not None:
            sections.setdefault(name.casefold(), _OfferingSection(name)).segments.append(segment)
    return list(sections.values())


# Journeys (ADR-0096) -----------------------------------------------------------------------

_JOURNEY_HEADING = re.compile(r"^journey\s*:\s*(?P<name>.+)$", re.IGNORECASE)
# "10. Select Business Pro Plus": an activity's own heading in a journey's details.
_STEP_HEADING = re.compile(r"^(?P<number>\d+(?:\.\d+)?)\.\s+(?P<name>\S.*)$")
# "- **Input → Output:** Selection → Basket"
_BULLET = re.compile(r"^\s*[-*+]\s+\*\*(?P<key>[^*]+?)\s*:?\s*\*\*\s*:?\s*(?P<value>.*)$")
_ARROW = re.compile(r"\s*(?:→|->)\s*")
_DASH = re.compile(r"\s+[—–-]\s+")
_PHASE = frozenset({"phase"})
_TRACK = frozenset({"track"})
_SUPPORTING = frozenset({"supporting systems", "supporting system", "supported by", "supporting"})
_SYSTEM_FUNCTION = frozenset({"system function"})
_MODE = frozenset({"mode"})
_RULE_KIND = frozenset({"rule type", "rule"})
_CONDITION = frozenset({"condition outcome", "condition", "outcome"})
_BRANCH = frozenset({"branch"})
_GROUP = frozenset({"parallel group"})
_REJOIN = frozenset({"rejoin at", "rejoin"})
_TIMING = frozenset({"sync async", "timing"})
_CORRELATION = frozenset({"correlation key"})


def _journey_name(segment: ExtractionSegment) -> str | None:
    """The journey a segment belongs to: the nearest "Journey: X" heading above it."""
    for heading in reversed(segment.section):
        if match := _JOURNEY_HEADING.match(plain_name(heading)):
            return match["name"].strip()
    return None


def _systems(cell: str, names: _Names) -> tuple[str, ...]:
    """The systems a cell names, split at "|", "," and ";", and at "/" unless one is named so."""
    found: list[str] = []
    for entry in re.split(r"[|,;]", cell.replace("\\|", "|")):
        name = plain_name(entry.strip())
        if not name or name in _NOTHING:
            continue
        parts = (
            [name]
            if names.known(name) or "/" not in name
            else [part.strip() for part in name.split("/") if part.strip()]
        )
        found.extend(names.resolve(part) for part in parts)
    return tuple(dict.fromkeys(found))


def _value(text: str) -> str | None:
    cleaned = text.replace("\\|", "|").strip()
    return None if cleaned in _NOTHING else cleaned


@dataclass
class _Details:
    """What an activity's own section says: its description and its "**Key:** value" bullets."""

    title: str
    description: list[str] = field(default_factory=list)
    facts: dict[str, str] = field(default_factory=dict)

    def fill(self, activity: Activity, names: _Names, offering: ProductOffering | None) -> Activity:
        """The activity with the gaps its table row left filled from here."""
        facts = self.facts
        phase, _, track = (facts.get("phase track") or "").partition("/")
        performer, _, supporting = (facts.get("performing system") or "").partition(";")
        supporting = re.sub(r"^\s*supporting\s*:?", "", supporting, flags=re.IGNORECASE)
        performers = _systems(performer, names)
        start, end = [*_ARROW.split(facts.get("input output") or "", maxsplit=1), ""][:2]
        evidence = _DASH.split(facts.get("evidence") or "", maxsplit=1)
        trust = _CONFIDENCE.get(evidence[0].strip().upper())
        components: list[str] = []
        for entry in (facts.get("related components") or facts.get("components") or "").split(","):
            name = _value(entry)
            if name:
                part = find_offering_component(offering, name) if offering else None
                components.append(part.id if part else name)
        return replace(
            activity,
            phase=activity.phase or _value(phase),
            track=activity.track or _value(track),
            performing_system_id=activity.performing_system_id
            or (performers[0] if performers else None),
            supporting_system_ids=activity.supporting_system_ids or _systems(supporting, names),
            system_function=activity.system_function or _value(facts.get("system function", "")),
            mode=activity.mode or _value(facts.get("mode", "")),
            customer_visible=(
                activity.customer_visible
                if activity.customer_visible is not None
                else _yes(facts.get("customer visible", ""))
            ),
            description=activity.description or "\n\n".join(self.description) or None,
            component_ids=activity.component_ids or tuple(dict.fromkeys(components)),
            input=activity.input or _value(start),
            output=activity.output or _value(end),
            etom=activity.etom or _value(facts.get("etom", "")),
            confidence=activity.confidence or (SourceConfidence(trust) if trust else None),
            source=activity.source or (_value(evidence[1]) if len(evidence) > 1 else None),
        )


@dataclass
class _JourneySection:
    """One "Journey: X" section of a document, read into one journey suggestion."""

    name: str
    # The product section it follows or sits in, as the document names it.
    product: str | None = None
    heading: ExtractionSegment | None = None
    segments: list[ExtractionSegment] = field(default_factory=list)

    def read_into(
        self, reading: TableReading, names: _Names, offering: ProductOffering | None
    ) -> None:
        steps: dict[str, Activity] = {}
        rules: list[FlowRule] = []
        links: list[ActivityIntegration] = []
        details: dict[str, _Details] = {}
        # Taken whole, or taken but still worth the model's look for capabilities.
        consumed: set[int] = set()
        read: set[int] = set()
        titles = {segment.section[-1] for segment in self.segments if segment.section} - {self.name}
        try:
            for segment in self.segments:
                if segment.cells:
                    self._row(_row(segment), steps, rules, links, consumed, read, names)
                    continue
                text = segment.text.strip()
                if plain_name(text) in titles and _STEP_HEADING.match(plain_name(text)):
                    consumed.add(segment.number)
                    continue
                step = (
                    _STEP_HEADING.match(plain_name(segment.section[-1]))
                    if segment.section
                    else None
                )
                if step is not None:
                    detail = details.setdefault(step["number"], _Details(step["name"].strip()))
                    bullets = [_BULLET.match(line) for line in text.splitlines()]
                    if any(bullets):
                        consumed.add(segment.number)
                        for bullet in bullets:
                            if bullet:
                                detail.facts[_column(bullet["key"])] = bullet["value"].strip()
                    else:
                        read.add(segment.number)
                        detail.description.append(text)
                elif text.startswith("```") or "-->" in text:
                    # The drawn flow: derived from the activities and rules, never read.
                    consumed.add(segment.number)
            for number, detail in details.items():
                steps[number] = detail.fill(
                    steps.get(number) or Activity(number, detail.title), names, offering
                )
            if not steps:
                return
            order = find_order_type(offering, self.name) if offering else None
            product = offering.id if offering else self.product
            journey = Journey(
                id=slug(f"{product} {self.name}" if product else self.name),
                name=self.name,
                product_id=product,
                order_type_code=order.code if order else None,
                activities=tuple(steps.values()),
                flow_rules=tuple(rules),
                integrations=tuple(links),
            )
        except InvalidKnowledgeError as exc:
            reading.notes.append(f"The journey {self.name} could not be read: {exc}")
            return
        reading.consumed |= consumed
        reading.read |= read - consumed
        cited = self.heading or self.segments[0]
        reading.changes.append(
            ProposedChange(
                CandidateContent(
                    CandidateKind.JOURNEY, journey.id, name=journey.name, journey=journey
                ),
                (cited.location,),
                cited.text,
                source_name=journey.name,
                reader=(READER, READER_VERSION),
            )
        )

    @staticmethod
    def _row(
        row: _Row,
        steps: dict[str, Activity],
        rules: list[FlowRule],
        links: list[ActivityIntegration],
        consumed: set[int],
        read: set[int],
        names: _Names,
    ) -> None:
        """One table row of the journey: an activity, a flow rule or an integration."""
        columns = frozenset(row.values)
        number = row.segment.number
        source = row.get(_SOURCE) or None
        if row.shape == "activity":
            read.add(number)
            step, name = row.get(_NUMBER), row.get(_ACTIVITY)
            if step and name and step not in steps:
                performers = _systems(row.get(_PERFORMER), names)
                steps[step] = Activity(
                    step,
                    name,
                    phase=row.get(_PHASE) or None,
                    track=row.get(_TRACK) or None,
                    performing_system_id=performers[0] if performers else None,
                    supporting_system_ids=_systems(row.get(_SUPPORTING), names),
                    system_function=row.get(_SYSTEM_FUNCTION) or None,
                    mode=row.get(_MODE) or None,
                    customer_visible=_yes(row.get(_VISIBLE)),
                    confidence=_trust(row),
                    source=source,
                )
        elif row.shape == "integration":
            if row.get(_FROM) and row.get(_TO):
                links.append(
                    ActivityIntegration(
                        row.get(_FROM),
                        row.get(_TO),
                        interaction=row.get(_INTERACTION) or None,
                        interface=row.get(_INTERFACE) or None,
                        payload=row.get(_PAYLOAD) or None,
                        timing=row.get(_TIMING) or None,
                        correlation_key=row.get(_CORRELATION) or None,
                        confidence=_trust(row),
                        source=source,
                    )
                )
        elif columns & _RULE_KIND and columns & _FROM and columns & _TO:
            consumed.add(number)
            if row.get(_RULE_KIND) and row.get(_FROM) and row.get(_TO):
                rules.append(
                    FlowRule(
                        flow_rule_kind(row.get(_RULE_KIND)),
                        row.get(_FROM),
                        row.get(_TO),
                        condition=row.get(_CONDITION) or None,
                        branch=row.get(_BRANCH) or None,
                        parallel_group=row.get(_GROUP) or None,
                        rejoin_at=row.get(_REJOIN) or None,
                        confidence=_trust(row),
                        source=source,
                    )
                )


def _journey_sections(segments: tuple[ExtractionSegment, ...]) -> list[_JourneySection]:
    """Each journey's segments, and the product section it follows or sits in."""
    sections: dict[str, _JourneySection] = {}
    product: str | None = None
    for segment in segments:
        text = plain_name(segment.text) if not segment.cells else ""
        heading = _PRODUCT_HEADING.match(text)
        if heading and _product_name(segment) is None:
            product = heading["name"].strip()
        journey = _JOURNEY_HEADING.match(text)
        name = _journey_name(segment)
        if journey and name is None:
            key = journey["name"].strip()
            section = sections.setdefault(key.casefold(), _JourneySection(key))
            section.heading = segment
            section.product = _product_name(segment) or product
            continue
        if name is not None:
            sections.setdefault(name.casefold(), _JourneySection(name)).segments.append(segment)
    return [item for item in sections.values() if item.segments]


class TableFirstCatalogueExtractor:
    """Tables read exactly first; the model reads what is left (ADR-0093).

    Rows the reader takes whole are not sent; system rows are sent marked
    ``read`` so the model gives only their capabilities, and any system or
    dependency it proposes from them anyway is dropped as a duplicate.
    """

    def __init__(self, model: CatalogueExtractorPort, reader: CatalogueTableReader) -> None:
        self._model = model
        self._reader = reader

    @property
    def supports_images(self) -> bool:
        return self._model.supports_images

    @property
    def model(self) -> str:
        return self._model.model

    @property
    def prompt_version(self) -> str:
        return f"{self._model.prompt_version}+{READER_VERSION}"

    def propose(self, request: ExtractionRequest) -> CatalogueProposal:
        reading = self._reader.read(request)
        rest = tuple(
            replace(segment, read=segment.number in reading.read)
            for segment in request.segments
            if segment.number not in reading.consumed
        )
        warnings: list[str] = list(reading.notes)
        taken = len(reading.read | reading.consumed)
        if taken:
            warnings.append(f"{taken} table row(s) were read directly, without the model.")
        changes: list[ProposedChange] = []
        if rest:
            try:
                proposal = self._model.propose(replace(request, segments=rest))
            except CatalogueExtractionError as exc:
                if not reading.changes:
                    raise
                warnings.append(f"The model could not read the rest of the document. {exc}")
            else:
                warnings[:0] = proposal.warnings
                read_rows = {item.location for item in rest if item.read}
                changes = [
                    change
                    for change in proposal.changes
                    if change.content.kind not in _FROM_CELLS
                    or not set(change.locations) <= read_rows
                ]
        return CatalogueProposal(
            (*reading.changes, *changes), self.model, self.prompt_version, tuple(warnings)
        )
