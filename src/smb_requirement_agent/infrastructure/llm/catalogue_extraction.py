"""Structured catalogue proposals from architecture documents, checked before use."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import deque
from dataclasses import dataclass, replace
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from smb_requirement_agent.application.errors import ModelTransportError
from smb_requirement_agent.application.ports.catalogue_extractor import (
    CatalogueAnswerUnusableError,
    CatalogueCitationError,
    CatalogueExtractionError,
    CatalogueExtractionUnsupportedError,
    CatalogueProposal,
    ExtractionRequest,
    ExtractionSegment,
    KnownSystem,
    ProposedChange,
)
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateBasis,
    CandidateContent,
    CandidateKind,
)
from smb_requirement_agent.domain.architecture.journeys import (
    Activity,
    FlowRule,
    FlowRuleKind,
    Journey,
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
    merge_components,
)
from smb_requirement_agent.infrastructure.llm.prompts.catalogue_extraction_prompt import (
    LEAN_SYSTEM_PROMPT,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from smb_requirement_agent.infrastructure.llm.structured_output import (
    StructuredOutputClient,
    StructuredOutputError,
    truncated,
)

_MAX_NAME = 200
_MAX_TEXT = 1000
_MAX_REASONING = 300


_Confidence = Literal["confirmed", "inferred", "gap"] | None
# Schema words the model never needs: titles, class descriptions, and the size limits, which
# validation still enforces. Left out, the schema costs a small model far less room.
_NOISE = ("title", "description", "maxLength", "maxItems")


def _compact(schema: dict[str, Any]) -> None:
    def strip(node: object) -> None:
        if isinstance(node, dict):
            for key in _NOISE:
                node.pop(key, None)
            for value in node.values():
                strip(value)
        elif isinstance(node, list):
            for value in node:
                strip(value)

    strip(schema)


class _Output(BaseModel):
    """An answer shape sent to the model; its schema is compact."""

    model_config = ConfigDict(json_schema_extra=_compact)


class ResponsibilityOutput(_Output):
    system: str = Field(max_length=_MAX_NAME)
    role: str = Field(max_length=_MAX_NAME)
    description: str = Field(max_length=_MAX_TEXT)
    order_types: list[str] = Field(max_length=20)
    confidence: _Confidence


class ComponentOutput(_Output):
    name: str = Field(max_length=_MAX_NAME)
    code: str | None = Field(max_length=_MAX_NAME)
    type: str | None = Field(max_length=_MAX_NAME)
    mandatory: bool | None
    customer_visible: bool | None
    description: str | None = Field(max_length=_MAX_TEXT)
    responsibilities: list[ResponsibilityOutput] = Field(max_length=40)
    confidence: _Confidence


class OrderTypeOutput(_Output):
    name: str = Field(max_length=_MAX_NAME)
    code: str | None = Field(max_length=_MAX_NAME)
    enabled: bool | None
    description: str | None = Field(max_length=_MAX_TEXT)
    confidence: _Confidence


class PointOutput(_Output):
    name: str = Field(max_length=_MAX_NAME)
    description: str | None = Field(max_length=_MAX_TEXT)


class OfferingOutput(_Output):
    """A product offering as the model read it; tidied into a valid one before use."""

    code: str | None = Field(max_length=_MAX_NAME)
    family: str | None = Field(max_length=_MAX_NAME)
    version: str | None = Field(max_length=_MAX_NAME)
    lifecycle: str | None = Field(max_length=_MAX_NAME)
    proposition: str | None = Field(max_length=_MAX_TEXT)
    rules: list[str] = Field(max_length=20)
    order_types: list[OrderTypeOutput] = Field(max_length=20)
    components: list[ComponentOutput] = Field(max_length=40)
    values: list[PointOutput] = Field(max_length=20)
    audiences: list[PointOutput] = Field(max_length=20)
    confidence: _Confidence


class StepOutput(_Output):
    number: str = Field(max_length=_MAX_NAME)
    name: str = Field(max_length=_MAX_NAME)
    track: str | None = Field(max_length=_MAX_NAME)
    system: str | None = Field(max_length=_MAX_NAME)
    supporting: list[str] = Field(max_length=20)
    function: str | None = Field(max_length=_MAX_TEXT)


class RuleOutput(_Output):
    kind: Literal["decision", "loop", "parallel"]
    from_step: str = Field(max_length=_MAX_NAME)
    to_step: str = Field(max_length=_MAX_NAME)
    condition: str | None = Field(max_length=_MAX_NAME)
    rejoin: str | None = Field(max_length=_MAX_NAME)


class JourneyOutput(_Output):
    """A journey as the model read it: kept lean, since it is the largest answer shape."""

    product: str | None = Field(max_length=_MAX_NAME)
    order_type: str | None = Field(max_length=_MAX_NAME)
    steps: list[StepOutput] = Field(max_length=100)
    rules: list[RuleOutput] = Field(max_length=100)


_LeanKind = Literal[
    "system",
    "component",
    "capability",
    "constraint",
    "relationship",
    "landscape_domain",
    "placement",
    "product_offering",
]


class LeanChangeOutput(_Output):
    """One suggestion, for a model whose context has no room for journeys (ADR-0096)."""

    kind: _LeanKind
    system: str = Field(max_length=_MAX_NAME)
    name: str | None = Field(max_length=_MAX_NAME)
    name_ar: str | None = Field(max_length=_MAX_NAME)
    aliases: list[str] = Field(max_length=20)
    triggers: list[str] = Field(max_length=20)
    target_system: str | None = Field(max_length=_MAX_NAME)
    # The component a capability belongs to, as named; null for other kinds.
    component: str | None = Field(max_length=_MAX_NAME)
    technology: str | None = Field(max_length=_MAX_NAME)
    # Where systems sit (ADR-0094): a placement's domain, and a landscape domain's parent,
    # as named; null for other kinds.
    domain: str | None = Field(max_length=_MAX_NAME)
    parent_domain: str | None = Field(max_length=_MAX_NAME)
    # The whole offering, for a product_offering; null for other kinds (ADR-0095).
    offering: OfferingOutput | None
    text: str | None = Field(max_length=_MAX_TEXT)
    evidence_numbers: list[int] = Field(min_length=1, max_length=10)
    quote: str = Field(max_length=_MAX_TEXT)
    basis: Literal["stated", "implied"]
    reasoning: str | None = Field(max_length=_MAX_REASONING)
    relationship_kind: (
        Literal[
            "calls_api", "publishes_events_to", "transfers_data_to", "orchestrates", "unspecified"
        ]
        | None
    )


class ChangeOutput(LeanChangeOutput):
    kind: _LeanKind | Literal["journey"]  # type: ignore[assignment]
    # The whole journey, for a journey; null for other kinds (ADR-0096).
    journey: JourneyOutput | None


class ExtractionOutput(_Output):
    # Generous, so a long but valid answer is never refused: how much one call
    # is asked to cover is decided by batching, not by this cap.
    changes: list[ChangeOutput] = Field(max_length=200)


class LeanExtractionOutput(_Output):
    changes: list[LeanChangeOutput] = Field(max_length=200)


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:80] or "item"


def _normalise(value: str) -> str:
    return " ".join(value.casefold().split())


def _clean(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.strip() for item in values if item.strip()))


# Joiners, variation selectors and the keycap mark that build emoji from parts.
_EMOJI_PARTS = frozenset({"‍", "⃣", "︎", "️"})


def plain_name(value: str) -> str:
    """A system name without the pictographs a landscape decorates it with.

    "📈 BCRM" and "🛠️ WFM / Remedy" are the systems BCRM and WFM / Remedy; the
    symbol is styling, and kept it would make the name differ from every other
    mention of the system. Letters, digits and punctuation are untouched.
    """
    kept = "".join(
        character
        for character in value
        if character not in _EMOJI_PARTS
        and unicodedata.category(character) != "So"
        # Emoji skin-tone modifiers; other modifier symbols (such as "^") stay.
        and not (unicodedata.category(character) == "Sk" and ord(character) >= 0x1F000)
    )
    return " ".join(kept.split())


def _plain(item: ChangeOutput) -> ChangeOutput:
    """The model's item with every system name written plainly; quotes stay verbatim."""
    return item.model_copy(
        update={
            "system": plain_name(item.system),
            "name": plain_name(item.name) if item.name is not None else None,
            "aliases": [plain_name(alias) for alias in item.aliases],
            "target_system": (
                plain_name(item.target_system) if item.target_system is not None else None
            ),
        }
    )


class _SystemNames:
    """Resolves how the model named a system to a catalogue id."""

    def __init__(self, known: tuple[KnownSystem, ...], proposed: list[ChangeOutput]) -> None:
        self._ids: dict[str, str] = {}
        for system in known:
            for label in (system.id, system.name, *system.aliases):
                self._ids.setdefault(label.casefold().strip(), system.id)
        for item in proposed:
            if item.kind == "system" and (item.name or item.system).strip():
                name = (item.name or item.system).strip()
                for label in (item.system, name, *item.aliases):
                    self._ids.setdefault(label.casefold().strip(), slug(name))

    def resolve(self, reference: str) -> str:
        key = reference.casefold().strip()
        return self._ids.get(key, slug(reference))


def _proposed(
    item: ChangeOutput, names: _SystemNames, locations: tuple[str, ...], quote: str
) -> ProposedChange:
    """A checked proposal, or InvalidKnowledgeError when the model's item cannot be used.

    Only a dependency can be implied, and an implied one must say why.
    """
    implied = item.basis == "implied"
    reasoning = (item.reasoning or "").strip()
    if implied and (item.kind != "relationship" or not reasoning):
        raise InvalidKnowledgeError("An implied item must be a dependency with its reasoning.")
    content = _content(item, names)
    source = (
        (item.name or item.system)
        if content.kind
        in {
            CandidateKind.SYSTEM,
            CandidateKind.LANDSCAPE_DOMAIN,
            CandidateKind.PRODUCT,
            CandidateKind.JOURNEY,
        }
        else item.system
    )
    return ProposedChange(
        content,
        locations,
        quote,
        source_name=source.strip(),
        target_name=(item.target_system or "").strip(),
        basis=CandidateBasis.INFERRED if implied else CandidateBasis.STATED,
        rationale=reasoning if implied else None,
    )


def domain_key(name: str, parent: str | None = None) -> str:
    """A landscape domain's key from its name: a sub-domain's says where it sits,
    "customer-assisted", as the table reader and the editor write it."""
    return slug(f"{parent} {name}" if parent else name)


def _text(value: str | None) -> str | None:
    return (value or "").strip() or None


def _trust(value: str | None) -> SourceConfidence | None:
    return SourceConfidence(value) if value else None


def _offering(item: ChangeOutput, names: _SystemNames) -> ProductOffering:
    """The model's offering made valid: order types keyed once, components by id, each
    system named once per role, and only order types the offering has."""
    read = item.offering
    name = (item.name or item.system).strip()
    if read is None:
        return ProductOffering(slug(name), name)
    orders: list[OrderType] = []
    keys: dict[str, str] = {}
    for order in read.order_types:
        title = order.name.strip()
        code = (order.code or "").strip() or "_".join(title.upper().split())
        if not title or code.casefold() in keys:
            continue
        keys[title.casefold()] = keys[code.casefold()] = code
        orders.append(
            OrderType(
                code,
                title,
                order.enabled is not False,
                _text(order.description),
                _trust(order.confidence),
            )
        )
    parts: dict[str, OfferingComponent] = {}
    for part in read.components:
        title = part.name.strip()
        if not title:
            continue
        duties: dict[tuple[str, str], ComponentResponsibility] = {}
        for duty in part.responsibilities:
            system, role, text = (
                plain_name(duty.system),
                duty.role.strip(),
                duty.description.strip(),
            )
            if not (system and role and text):
                continue
            found = ComponentResponsibility(
                names.resolve(system),
                role,
                text,
                tuple(
                    keys[key]
                    for key in (code.casefold() for code in duty.order_types)
                    if key in keys
                ),
                _trust(duty.confidence),
            )
            duties.setdefault((found.system_id, found.role), found)
        component = OfferingComponent(
            slug(part.code or title),
            title,
            code=_text(part.code),
            kind=_text(part.type),
            mandatory=part.mandatory,
            customer_visible=part.customer_visible,
            description=_text(part.description),
            responsibilities=tuple(duties.values()),
            confidence=_trust(part.confidence),
        )
        previous = parts.get(component.id)
        parts[component.id] = merge_components(previous, component) if previous else component

    def points(items: list[PointOutput]) -> tuple[OfferingPoint, ...]:
        found = {item.name.strip().casefold(): item for item in items if item.name.strip()}
        return tuple(
            OfferingPoint(item.name.strip(), _text(item.description)) for item in found.values()
        )

    offering_code = _text(read.code)
    return ProductOffering(
        id=slug(offering_code or name),
        name=name,
        code=offering_code,
        family=_text(read.family),
        version=_text(read.version),
        lifecycle=_text(read.lifecycle),
        proposition=_text(read.proposition),
        rules=tuple(dict.fromkeys(rule.strip() for rule in read.rules if rule.strip())),
        order_types=tuple(orders),
        components=tuple(parts.values()),
        values=points(read.values),
        audiences=points(read.audiences),
        confidence=_trust(read.confidence),
    )


def _journey(item: ChangeOutput, names: _SystemNames) -> Journey:
    """The model's journey made valid: each activity number once, and only rules between
    activities it has; the offering, order type and systems are resolved when accepted."""
    read = item.journey
    name = (item.name or item.system).strip()
    product = _text(read.product) if read else None
    steps: dict[str, Activity] = {}
    rules: list[FlowRule] = []
    for step in read.steps if read else []:
        number, title = step.number.strip(), step.name.strip()
        if not number or not title or number in steps:
            continue
        performer = plain_name(step.system or "")
        steps[number] = Activity(
            number,
            title,
            track=_text(step.track),
            performing_system_id=names.resolve(performer) if performer else None,
            supporting_system_ids=tuple(
                dict.fromkeys(
                    names.resolve(plain_name(other))
                    for other in step.supporting
                    if plain_name(other)
                )
            ),
            system_function=_text(step.function),
        )
    for rule in read.rules if read else []:
        start, end = rule.from_step.strip(), rule.to_step.strip()
        rejoin = _text(rule.rejoin) if rule.kind == "parallel" else None
        if start in steps and end in steps and (rejoin is None or rejoin in steps):
            rules.append(
                FlowRule(
                    FlowRuleKind(rule.kind), start, end, _text(rule.condition), None, None, rejoin
                )
            )
    return Journey(
        id=slug(f"{product} {name}" if product else name),
        name=name,
        product_id=product,
        order_type_code=_text(read.order_type) if read and product else None,
        activities=tuple(steps.values()),
        flow_rules=tuple(rules),
    )


def _content(item: ChangeOutput, names: _SystemNames) -> CandidateContent:
    if item.kind == "journey":
        journey = _journey(item, names)
        return CandidateContent(
            CandidateKind.JOURNEY, journey.id, name=journey.name, journey=journey
        )
    if item.kind == "product_offering":
        offering = _offering(item, names)
        return CandidateContent(
            CandidateKind.PRODUCT, offering.id, name=offering.name, product=offering
        )
    kind = CandidateKind(item.kind)
    name = (item.name or "").strip()
    if kind is CandidateKind.LANDSCAPE_DOMAIN:
        parent = (item.parent_domain or "").strip() or None
        key = domain_key(name, parent)
        return CandidateContent(
            kind,
            key,
            name=name,
            name_ar=(item.name_ar or "").strip() or None,
            landscape_domain_id=key,
            parent_domain_id=slug(parent) if parent else None,
            description=(item.text or "").strip() or None,
        )
    if kind is CandidateKind.SYSTEM:
        name = name or item.system.strip()
        return CandidateContent(
            kind,
            names.resolve(item.system or name),
            name=name,
            name_ar=(item.name_ar or "").strip() or None,
            aliases=tuple(
                alias for alias in _clean(item.aliases) if alias.casefold() != name.casefold()
            ),
            description=(item.text or "").strip() or None,
        )
    if kind is CandidateKind.PLACEMENT:
        place = (item.domain or "").strip()
        parent = (item.parent_domain or "").strip() or None
        return CandidateContent(
            kind,
            names.resolve(item.system),
            # A sub-domain is keyed under its parent; a bare name still finds a domain
            # that alone has it.
            landscape_domain_id=domain_key(place, parent) if place else "",
        )
    system_id = names.resolve(item.system)
    if kind is CandidateKind.COMPONENT:
        return CandidateContent(
            kind,
            system_id,
            name=name,
            name_ar=(item.name_ar or "").strip() or None,
            aliases=tuple(
                alias for alias in _clean(item.aliases) if alias.casefold() != name.casefold()
            ),
            component_id=slug(name),
            description=(item.text or "").strip() or None,
            technology=(item.technology or "").strip() or None,
        )
    if kind is CandidateKind.CAPABILITY:
        component = (item.component or "").strip()
        return CandidateContent(
            kind,
            system_id,
            name=name,
            capability_id=slug(name),
            triggers=_clean(item.triggers),
            component_id=slug(component) if component else None,
        )
    if kind is CandidateKind.CONSTRAINT:
        return CandidateContent(kind, system_id, text=(item.text or "").strip())
    return CandidateContent(
        kind,
        system_id,
        target_system_id=names.resolve(item.target_system or ""),
        text=(item.text or "").strip(),
        relationship_kind=RelationshipKind(item.relationship_kind or "unspecified"),
    )


_QUOTE_OVERLAP = 0.6
_MAX_QUOTE = 300
# Each call's text stays below this even with a very large context window, so
# a single answer is not asked to cover a whole book.
MAX_TEXT_CHARACTERS_PER_CALL = 48_000
# Below this much room for document text, reading is not worth attempting.
_MIN_TEXT_TOKENS = 400
_IMAGE_TOKENS = 1024
_SCHEMA_TEXT = json.dumps(ExtractionOutput.model_json_schema())
_LEAN_SCHEMA_TEXT = json.dumps(LeanExtractionOutput.model_json_schema())
# With less room than this for document text, a reading leaves journeys out (ADR-0096).
_JOURNEY_ROOM = 4 * _MIN_TEXT_TOKENS
_JOURNEY_WORD = re.compile(r"\bjourneys?\b", re.IGNORECASE)
# Each part of a document is asked for at most this many times.
_ATTEMPTS = 2
# What one suggestion costs in the answer, keys and quote included, and how much
# document text one answer token covers in a dense catalogue table. Together they
# size a call so its answer fits the model's output limit (ADR-0091).
_TOKENS_PER_CHANGE = 150
_CHARACTERS_PER_OUTPUT_TOKEN = 1.0
# Assumed when the client does not say how long its answers may be.
_DEFAULT_OUTPUT_TOKENS = 16_384
# Never ask a call for fewer suggestions than this, however small the model.
_MIN_CAPACITY = 10
# A part whose answer was cut off, or filled up, is split and asked again at
# most this many times over; a passage shorter than this is not split.
_MAX_SPLIT_DEPTH = 4
_MIN_SPLIT_CHARACTERS = 400
_REASONS = {
    "unusable": "the model's answer was unusable.",
    "uncited": "no suggestion cited the text correctly.",
    "truncated": "the model's answer was too long, even for a small part.",
    "budget": "the reading reached its limit on model calls.",
}
# Provider failures that asking again cannot fix.
_PERMANENT_KINDS = {"authentication", "configuration", "payment"}


def _permanent(error: BaseException) -> bool:
    current: BaseException | None = error
    while current is not None:
        if isinstance(current, ModelTransportError):
            return current.kind in _PERMANENT_KINDS
        current = current.__cause__
    return False


def _tokens(text: str) -> int:
    """The transports' own estimate, so a batch that fits here fits there."""
    return len(text) // 4 + 1


def _words(value: str) -> set[str]:
    return {word for word in re.findall(r"\w+", value.casefold()) if len(word) > 2}


def _evidence_quote(quote: str, cited: list[ExtractionSegment]) -> str | None:
    """The verbatim text supporting a quote, or None when the segments do not say it.

    Small models often paraphrase. An exact quote is kept; a close paraphrase
    is replaced by the cited sentence it best matches, so what a person reads
    is always the document's own words.
    """
    normalised = _normalise(quote)
    if not normalised:
        return None
    if any(segment.image_mime_type for segment in cited):
        # A vision model reads an image; there is no text to match the quote against.
        return quote.strip()
    if any(normalised in _normalise(segment.text) for segment in cited):
        return quote.strip()
    wanted = _words(quote)
    if not wanted:
        return None
    best, best_overlap = None, 0.0
    for segment in cited:
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", segment.text):
            overlap = len(wanted & _words(sentence)) / len(wanted)
            if overlap > best_overlap and sentence.strip():
                best, best_overlap = sentence.strip(), overlap
    if best is None or best_overlap < _QUOTE_OVERLAP:
        return None
    return best if len(best) <= _MAX_QUOTE else best[: _MAX_QUOTE - 1].rstrip() + "…"


def _parts(segment: ExtractionSegment, limit: int) -> list[ExtractionSegment]:
    """A passage too long for one call, cut at line or word breaks, keeping its location."""
    if segment.image_mime_type or len(segment.text) <= limit:
        return [segment]
    pieces: list[str] = []
    remaining = segment.text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = remaining.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:]
    pieces.append(remaining.strip())
    pieces = [piece for piece in pieces if piece]
    return [
        ExtractionSegment(
            0,
            f"{segment.location} (part {index} of {len(pieces)})",
            piece,
            section=segment.section,
        )
        for index, piece in enumerate(pieces, start=1)
    ]


def _span(batch: list[ExtractionSegment]) -> str:
    first, last = batch[0].location, batch[-1].location
    return first if first == last else f"{first} to {last}"


def _halves(batch: list[ExtractionSegment]) -> list[list[ExtractionSegment]] | None:
    """A part split for asking again, in document order; None when it cannot be split."""
    if len(batch) > 1:
        # Cut where the headings change nearest the middle, so a table stays whole.
        middle = len(batch) // 2
        boundaries = [i for i in range(1, len(batch)) if batch[i].section != batch[i - 1].section]
        cut = min(boundaries, key=lambda i: abs(i - middle), default=middle)
        return [batch[:cut], batch[cut:]]
    segment = batch[0]
    if segment.image_mime_type or len(segment.text) < _MIN_SPLIT_CHARACTERS:
        return None
    pieces = _parts(segment, len(segment.text) // 2 + 1)
    return [[piece] for piece in pieces] if len(pieces) > 1 else None


@dataclass
class _Answer:
    """One call's checked changes, how many were dropped, and how many the model gave."""

    changes: list[ProposedChange]
    dropped: int
    given: int


class StructuredCatalogueExtractor:
    def __init__(
        self,
        client: StructuredOutputClient,
        *,
        supports_images: bool,
        max_input_tokens: int | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        """``max_input_tokens`` is the prompt room the client allows; None means ample.

        ``max_output_tokens`` is how long one answer may be; None means the
        client does not say, and a common hosted limit is assumed.
        """
        self._client = client
        self._supports_images = supports_images
        self._max_input_tokens = max_input_tokens
        self._output_tokens = max_output_tokens or _DEFAULT_OUTPUT_TOKENS
        # How many suggestions one answer can hold; an answer this long may have
        # been cut short by the model, so its part is split and asked again.
        self._capacity = max(_MIN_CAPACITY, int(self._output_tokens * 0.8) // _TOKENS_PER_CHANGE)

    @property
    def supports_images(self) -> bool:
        return self._supports_images

    @property
    def model(self) -> str:
        return self._client.model

    @property
    def prompt_version(self) -> str:
        return PROMPT_VERSION

    def _known(
        self, request: ExtractionRequest, budget: int, warnings: list[str]
    ) -> tuple[KnownSystem, ...]:
        """The catalogue given to the model, trimmed so document text still has room."""
        known = request.known_systems

        def cost(systems: tuple[KnownSystem, ...]) -> int:
            return _tokens(
                build_user_prompt(ExtractionRequest(request.document_title, (), systems))
            )

        if cost(known) <= budget // 3:
            return known
        known = tuple(KnownSystem(item.id, item.name, ()) for item in known)
        kept = len(known)
        while kept and cost(known[:kept]) > budget // 3:
            kept -= 1
        if kept < len(known):
            warnings.append(
                f"Only {kept} of {len(known)} catalogue systems were shown to the model; "
                "it may suggest some existing systems again."
            )
        return known[:kept]

    def _batches(
        self, segments: tuple[ExtractionSegment, ...], text_characters: int
    ) -> list[list[ExtractionSegment]]:
        batches: list[list[ExtractionSegment]] = []
        current: list[ExtractionSegment] = []
        size = 0
        for segment in (part for item in segments for part in _parts(item, text_characters)):
            if segment.image_mime_type:
                batches.append([segment])
                continue
            # The segment's JSON wrapping (number, location, section) costs a little too.
            cost = len(segment.text) + len(segment.location) + 40
            cost += sum(len(heading) + 3 for heading in segment.section)
            # Past half full, a new section starts a new call rather than splitting one.
            new_section = bool(current) and segment.section != current[-1].section
            if current and (
                size + cost > text_characters or (new_section and size >= text_characters // 2)
            ):
                batches.append(current)
                current, size = [], 0
            current.append(segment)
            size += cost
        if current:
            batches.append(current)
        return batches

    def propose(self, request: ExtractionRequest) -> CatalogueProposal:
        budget = self._max_input_tokens
        warnings: list[str] = []
        available = int(budget * 0.9) if budget is not None else 10**9
        room = available - _tokens(SYSTEM_PROMPT) - _tokens(_SCHEMA_TEXT)
        # A journey is the largest answer shape; a small context reads without it rather than
        # with too little room left for the document (ADR-0096).
        lean = room < _JOURNEY_ROOM
        if lean:
            room = available - _tokens(LEAN_SYSTEM_PROMPT) - _tokens(_LEAN_SCHEMA_TEXT)
            if any(
                _JOURNEY_WORD.search(" ".join((*item.section, item.text)))
                for item in request.segments
            ):
                warnings.append(
                    "This model's context is too small to also propose journeys from prose; "
                    "journeys set out in tables are still read."
                )
        if room < _MIN_TEXT_TOKENS * 2:
            raise CatalogueExtractionUnsupportedError(
                "The configured model's context window is too small to read documents. Raise "
                "LOCAL_LLM_CONTEXT_WINDOW_TOKENS (and the model server's context), or the "
                "profile's context_tokens, so at least 8,192 tokens are left for input."
            )
        known = self._known(request, room, warnings)
        known_cost = _tokens(
            build_user_prompt(ExtractionRequest(request.document_title, (), known))
        )
        # A call covers only as much text as one answer can hold suggestions for.
        text_characters = min(
            MAX_TEXT_CHARACTERS_PER_CALL,
            (room - known_cost) * 4,
            max(_MIN_TEXT_TOKENS * 4, int(self._output_tokens * _CHARACTERS_PER_OUTPUT_TOKEN)),
        )
        changes: list[ProposedChange] = []
        dropped = 0
        failures: list[tuple[str, str]] = []
        last_error: Exception | None = None
        read_any = False
        batches = self._batches(request.segments, text_characters)
        pending = deque((batch, 0) for batch in batches)
        # Splitting is bounded, so a document that every model answer overflows
        # still finishes in a predictable number of calls.
        calls_left = 3 * len(batches) + 4
        while pending:
            batch, depth = pending.popleft()
            if calls_left < 1:
                failures.append(
                    ("budget", f"{_span(batch)} could not be read: {_REASONS['budget']}")
                )
                continue
            request.checkpoint()
            numbered = tuple(
                replace(item, number=number) for number, item in enumerate(batch, start=1)
            )
            images = tuple(
                (item.image_mime_type, item.image) for item in numbered if item.image_mime_type
            )
            if images and room - known_cost < _IMAGE_TOKENS * len(images):
                failures.append(
                    ("image", f"{_span(batch)} is too large an image for the configured model.")
                )
                continue
            answer: _Answer | None = None
            reason = ""
            # Answers vary between calls, so a rejected one is asked for once more,
            # unless the parts still waiting need the calls left.
            for attempt in range(_ATTEMPTS):
                if attempt:
                    if calls_left <= len(pending):
                        break
                    request.checkpoint()
                calls_left -= 1
                try:
                    answer = self._read(request, numbered, known, images, lean=lean)
                except (StructuredOutputError, ValidationError, ModelTransportError) as exc:
                    last_error = exc
                    if truncated(exc):
                        # Asking for the same part again would be cut off again.
                        reason = "truncated"
                        break
                    reason = "unusable"
                    if _permanent(exc):
                        break
                    continue
                if answer is not None:
                    break
                reason = "uncited"
            full = reason == "truncated" or (answer is not None and answer.given >= self._capacity)
            halves = _halves(batch) if full and depth < _MAX_SPLIT_DEPTH else None
            if halves and calls_left >= len(pending) + len(halves):
                # A smaller part gets the whole answer to itself; the full answer
                # is set aside so its parts are not suggested twice.
                for half in reversed(halves):
                    pending.appendleft((half, depth + 1))
                continue
            if answer is None:
                failures.append((reason, f"{_span(batch)} could not be read: {_REASONS[reason]}"))
                continue
            read_any = True
            if full:
                warnings.append(
                    f"{_span(batch)} may not be read completely: the model's answer reached "
                    "its limit."
                )
            changes.extend(answer.changes)
            dropped += answer.dropped
        warnings.extend(message for _, message in failures)
        if failures and not read_any:
            message = f"No part of the document could be read by the model. {failures[-1][1]}"
            if all(reason == "uncited" for reason, _ in failures):
                raise CatalogueCitationError(message)
            if last_error is not None:
                raise CatalogueAnswerUnusableError(message) from last_error
            raise CatalogueExtractionError(message)
        if dropped:
            warnings.append(
                f"{dropped} suggestion(s) were left out because their citation "
                "could not be checked."
            )
        return CatalogueProposal(
            tuple(changes), self._client.model, PROMPT_VERSION, tuple(warnings)
        )

    def _read(
        self,
        request: ExtractionRequest,
        numbered: tuple[ExtractionSegment, ...],
        known: tuple[KnownSystem, ...],
        images: tuple[tuple[str, bytes], ...],
        *,
        lean: bool = False,
    ) -> _Answer | None:
        """One call's checked changes and how many were dropped.

        None when the model suggested something but none of it cited the text
        correctly: that part of the document was not read. A ``lean`` call asks
        without journeys, for a model whose context has no room for them.
        """
        prompt = build_user_prompt(ExtractionRequest(request.document_title, numbered, known))
        if lean:
            answered = self._client.parse(
                system_prompt=LEAN_SYSTEM_PROMPT,
                user_prompt=prompt,
                schema_type=LeanExtractionOutput,
                images=images,
            )
            output = ExtractionOutput(
                changes=[
                    ChangeOutput.model_validate({**item.model_dump(), "journey": None})
                    for item in answered.changes
                ]
            )
        else:
            output = self._client.parse(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
                schema_type=ExtractionOutput,
                images=images,
            )
        segments = {item.number: item for item in numbered}
        given = [_plain(item) for item in output.changes]
        names = _SystemNames(request.known_systems, given)
        changes: list[ProposedChange] = []
        dropped = 0
        for item in given:
            cited = [segments[n] for n in dict.fromkeys(item.evidence_numbers) if n in segments]
            quote = (
                _evidence_quote(item.quote, cited)
                if len(cited) == len(set(item.evidence_numbers))
                else None
            )
            if quote is None:
                dropped += 1
                continue
            try:
                change = _proposed(item, names, tuple(segment.location for segment in cited), quote)
            except InvalidKnowledgeError:
                dropped += 1
                continue
            changes.append(change)
        if output.changes and not changes:
            return None
        return _Answer(changes, dropped, len(output.changes))


class FakeCatalogueExtractor:
    """Deterministic offline extraction from labelled lines; not a language model.

    Recognises ``System: Name``, ``Component: Name [technology]``,
    ``Capability: Name (phrase, phrase) @ Component``, ``Constraint: text`` (all
    three for the last system named; the technology and component are optional),
    ``A depends on B for reason`` and ``A calls B for reason`` lines (the second
    as an API call), and reads ``A sends X to B`` as an inferred data transfer.
    An image yields one system named after the document so the review flow can
    be exercised without a vision model.
    """

    _SYSTEM = re.compile(r"^system:\s*(?P<name>.+)$", re.IGNORECASE)
    _COMPONENT = re.compile(
        r"^component:\s*(?P<name>[^\[]+?)\s*(?:\[(?P<technology>[^\]]+)\])?$", re.I
    )
    _CAPABILITY = re.compile(
        r"^capability:\s*(?P<name>[^(]+)\((?P<triggers>[^)]+)\)(?:\s*@\s*(?P<component>.+))?",
        re.I,
    )
    _CONSTRAINT = re.compile(r"^constraint:\s*(?P<text>.+)$", re.IGNORECASE)
    _DEPENDS = re.compile(
        r"^(?P<source>.+?)\s+(?P<verb>depends on|calls)\s+(?P<target>.+?)"
        r"(?:\s+(?:for|to)\s+(?P<why>.+?))?\.?$",
        re.IGNORECASE,
    )
    _SENDS = re.compile(
        r"^(?P<source>.+?)\s+(?:sends|posts|pushes)\s+(?P<what>.+?)\s+to\s+(?P<target>.+?)\.?$",
        re.IGNORECASE,
    )

    supports_images = True
    model = "fake-catalogue-extractor"
    prompt_version = PROMPT_VERSION

    def propose(self, request: ExtractionRequest) -> CatalogueProposal:
        known: dict[str, str] = {}
        for system in request.known_systems:
            for label in (system.id, system.name, *system.aliases):
                known[label.casefold()] = system.id
        changes: list[ProposedChange] = []
        current: str | None = None
        current_name = ""

        def system_id(name: str) -> str:
            return known.setdefault(name.casefold().strip(), slug(name))

        for segment in request.segments:
            request.checkpoint()
            if segment.image_mime_type:
                name = request.document_title.strip()
                changes.append(
                    ProposedChange(
                        CandidateContent(CandidateKind.SYSTEM, system_id(name), name=name),
                        (segment.location,),
                        name,
                    )
                )
                continue
            for line in (raw.strip() for raw in segment.text.splitlines()):
                source_name, target_name = current_name, ""
                basis, rationale = CandidateBasis.STATED, None
                if match := self._SYSTEM.match(line):
                    name = match["name"].strip()
                    current, current_name = system_id(name), name
                    source_name = name
                    content = CandidateContent(CandidateKind.SYSTEM, current, name=name)
                elif (match := self._COMPONENT.match(line)) and current:
                    name = match["name"].strip()
                    content = CandidateContent(
                        CandidateKind.COMPONENT,
                        current,
                        name=name,
                        component_id=slug(name),
                        technology=(match["technology"] or "").strip() or None,
                    )
                elif (match := self._CAPABILITY.match(line)) and current:
                    name = match["name"].strip()
                    component = (match["component"] or "").strip()
                    content = CandidateContent(
                        CandidateKind.CAPABILITY,
                        current,
                        name=name,
                        capability_id=slug(name),
                        triggers=_clean(match["triggers"].split(",")),
                        component_id=slug(component) if component else None,
                    )
                elif (match := self._CONSTRAINT.match(line)) and current:
                    content = CandidateContent(
                        CandidateKind.CONSTRAINT, current, text=match["text"].strip()
                    )
                elif match := self._DEPENDS.match(line) or self._SENDS.match(line):
                    source_name, target_name = match["source"].strip(), match["target"].strip()
                    sends = match.re is self._SENDS
                    calls = not sends and match["verb"].casefold() == "calls"
                    content = CandidateContent(
                        CandidateKind.RELATIONSHIP,
                        system_id(source_name),
                        target_system_id=system_id(target_name),
                        text=(
                            f"Sends {match['what'].strip()}"
                            if sends
                            else (match["why"] or ("Calls" if calls else "Depends on")).strip()
                        ),
                        relationship_kind=(
                            RelationshipKind.TRANSFERS_DATA_TO
                            if sends
                            else RelationshipKind.CALLS_API
                            if calls
                            else RelationshipKind.UNSPECIFIED
                        ),
                    )
                    if sends:
                        basis = CandidateBasis.INFERRED
                        rationale = (
                            f"{source_name} sends {match['what'].strip()} to {target_name}, "
                            f"so it relies on {target_name} to receive them."
                        )
                else:
                    continue
                changes.append(
                    ProposedChange(
                        content,
                        (segment.location,),
                        line,
                        source_name,
                        target_name,
                        basis,
                        rationale,
                    )
                )
        return CatalogueProposal(tuple(changes), self.model, self.prompt_version)
