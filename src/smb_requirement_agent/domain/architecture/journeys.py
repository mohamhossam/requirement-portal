"""Journeys: the ordered activities that fulfil an order, and the systems that perform them.

A journey such as Business Pro Plus › New Activation is a sequence of numbered
activities on a main track, with exceptions and side tracks set out as rules:
a decision branches ("PASS" to 80, "FAIL" to 75), a loop goes back ("Correct &
Resubmit" to 10), and parallel tracks run side by side until they rejoin. The
flow is never stored: ``journey_edges`` derives it from the order and the rules,
so a person edits activities and rules, not arrows (ADR-0096).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from smb_requirement_agent.domain.architecture.invariants import (
    InvalidKnowledgeError,
    optional,
    required,
)
from smb_requirement_agent.domain.architecture.products import (
    ProductOffering,
    SourceConfidence,
    check_source,
    first_known,
)

MAIN_TRACK = "MAIN"


def _codes(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(required(item, label) for item in values))


def activity_order(number: str) -> tuple[int, float, str]:
    """Activities sort by number as a number ("75" before "100"), then as text."""
    match = re.match(r"\d+(\.\d+)?", number)
    return (0, float(match.group(0)), number) if match else (1, 0.0, number)


@dataclass(frozen=True)
class Activity:
    number: str
    name: str
    phase: str | None = None
    # MAIN, or a side track such as FIELD or CORRECTION; None reads as MAIN.
    track: str | None = None
    performing_system_id: str | None = None
    supporting_system_ids: tuple[str, ...] = ()
    system_function: str | None = None
    # As the source says: "Automated", "Manual", "Hybrid".
    mode: str | None = None
    customer_visible: bool | None = None
    description: str | None = None
    component_ids: tuple[str, ...] = ()
    input: str | None = None
    output: str | None = None
    # Where it sits in eTOM, such as "Customer Relationship Management › Order Capture".
    etom: str | None = None
    confidence: SourceConfidence | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "number", required(self.number, "Activity number"))
        object.__setattr__(self, "name", required(self.name, "Activity name"))
        for field, label in (
            ("phase", "Phase"),
            ("track", "Track"),
            ("performing_system_id", "Performing system"),
            ("system_function", "System function"),
            ("mode", "Mode"),
            ("description", "Description"),
            ("input", "Input"),
            ("output", "Output"),
            ("etom", "eTOM"),
        ):
            object.__setattr__(self, field, optional(getattr(self, field), label))
        object.__setattr__(
            self, "supporting_system_ids", _codes(self.supporting_system_ids, "Supporting system")
        )
        object.__setattr__(self, "component_ids", _codes(self.component_ids, "Component"))
        check_source(self)

    @property
    def main(self) -> bool:
        return (self.track or MAIN_TRACK).casefold() == MAIN_TRACK.casefold()

    @property
    def systems(self) -> tuple[str, ...]:
        named = (self.performing_system_id,) if self.performing_system_id else ()
        return (*named, *self.supporting_system_ids)


class FlowRuleKind(StrEnum):
    DECISION = "decision"
    LOOP = "loop"
    PARALLEL = "parallel"


def flow_rule_kind(value: FlowRuleKind | str) -> FlowRuleKind:
    try:
        return FlowRuleKind(str(value).strip().casefold())
    except ValueError as exc:
        raise InvalidKnowledgeError(
            f"A flow rule is a decision, a loop or a parallel track, not {value!r}."
        ) from exc


@dataclass(frozen=True)
class FlowRule:
    """A way the flow leaves an activity other than to the next one on the main track."""

    kind: FlowRuleKind
    from_activity: str
    to_activity: str
    # What sends the flow this way, such as "PASS" or "Correct & Resubmit".
    condition: str | None = None
    # The branch or track it starts, such as "FAIL" or "FIELD".
    branch: str | None = None
    parallel_group: str | None = None
    # For a parallel track, the activity where it joins the main track again.
    rejoin_at: str | None = None
    confidence: SourceConfidence | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", flow_rule_kind(self.kind))
        object.__setattr__(self, "from_activity", required(self.from_activity, "From activity"))
        object.__setattr__(self, "to_activity", required(self.to_activity, "To activity"))
        for field, label in (
            ("condition", "Condition"),
            ("branch", "Branch"),
            ("parallel_group", "Parallel group"),
            ("rejoin_at", "Rejoin activity"),
        ):
            object.__setattr__(self, field, optional(getattr(self, field), label))
        check_source(self)


@dataclass(frozen=True)
class ActivityIntegration:
    """How one activity hands over to another: the interaction, interface and payload."""

    from_activity: str
    to_activity: str
    interaction: str | None = None
    interface: str | None = None
    payload: str | None = None
    # "Sync", "Async" or unknown, as the source says.
    timing: str | None = None
    correlation_key: str | None = None
    confidence: SourceConfidence | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "from_activity", required(self.from_activity, "From activity"))
        object.__setattr__(self, "to_activity", required(self.to_activity, "To activity"))
        for field, label in (
            ("interaction", "Interaction"),
            ("interface", "Interface"),
            ("payload", "Payload"),
            ("timing", "Timing"),
            ("correlation_key", "Correlation key"),
        ):
            object.__setattr__(self, field, optional(getattr(self, field), label))
        check_source(self)


@dataclass(frozen=True)
class JourneyEdge:
    """One arrow of the derived flow."""

    from_activity: str
    to_activity: str
    # "sequence" on the main track, or the kind of rule that made it, or "rejoin".
    kind: str
    label: str | None = None


@dataclass(frozen=True)
class Journey:
    id: str
    name: str
    # The offering and order type it fulfils, when it is one's (ADR-0095).
    product_id: str | None = None
    order_type_code: str | None = None
    description: str | None = None
    activities: tuple[Activity, ...] = ()
    flow_rules: tuple[FlowRule, ...] = ()
    integrations: tuple[ActivityIntegration, ...] = ()
    confidence: SourceConfidence | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", required(self.id, "Journey id"))
        object.__setattr__(self, "name", required(self.name, "Journey name"))
        for field, label in (
            ("product_id", "Product offering"),
            ("order_type_code", "Order type"),
            ("description", "Description"),
        ):
            object.__setattr__(self, field, optional(getattr(self, field), label))
        if self.order_type_code and not self.product_id:
            raise InvalidKnowledgeError(f"{self.name}: an order type needs its product offering.")
        check_source(self)
        numbers = [item.number for item in self.activities]
        if len(set(numbers)) != len(numbers):
            raise InvalidKnowledgeError(f"{self.name}: activity numbers must be unique.")
        known = set(numbers)
        for rule in self.flow_rules:
            for reference in (rule.from_activity, rule.to_activity, rule.rejoin_at):
                if reference is not None and reference not in known:
                    raise InvalidKnowledgeError(
                        f"{self.name}: a {rule.kind.value} rule names activity {reference!r}, "
                        "which is not in the journey."
                    )
        for link in self.integrations:
            for reference in (link.from_activity, link.to_activity):
                if reference not in known:
                    raise InvalidKnowledgeError(
                        f"{self.name}: an integration names activity {reference!r}, which is "
                        "not in the journey."
                    )

    @property
    def ordered(self) -> tuple[Activity, ...]:
        return tuple(sorted(self.activities, key=lambda item: activity_order(item.number)))

    @property
    def systems(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(system for item in self.ordered for system in item.systems))


def journey_edges(journey: Journey) -> tuple[JourneyEdge, ...]:
    """The flow: each main-track activity to the next, unless a rule leaves it, plus every
    rule, and each parallel track back to where it rejoins. Each arrow once."""
    edges: list[JourneyEdge] = []
    seen: set[tuple[str, str]] = set()

    def add(edge: JourneyEdge) -> None:
        if (edge.from_activity, edge.to_activity) not in seen:
            seen.add((edge.from_activity, edge.to_activity))
            edges.append(edge)

    leaving = {rule.from_activity for rule in journey.flow_rules}
    main = [item for item in journey.ordered if item.main]
    for current, following in zip(main, main[1:], strict=False):
        if current.number not in leaving:
            add(JourneyEdge(current.number, following.number, "sequence"))
    for rule in journey.flow_rules:
        add(
            JourneyEdge(
                rule.from_activity, rule.to_activity, rule.kind.value, rule.condition or rule.branch
            )
        )
        if rule.kind is FlowRuleKind.PARALLEL and rule.rejoin_at:
            add(JourneyEdge(rule.to_activity, rule.rejoin_at, "rejoin", "rejoin"))
    return tuple(edges)


def check_journeys(
    journeys: tuple[Journey, ...], system_ids: set[str], offerings: tuple[ProductOffering, ...]
) -> None:
    """Unique journeys whose systems, offerings, order types and components the release has.

    So a system, offering or component a journey names cannot be removed: the
    message says which journey and activity name it.
    """
    ids = [item.id for item in journeys]
    if len(set(ids)) != len(ids):
        raise InvalidKnowledgeError("Journey ids must be unique.")
    by_id = {item.id: item for item in offerings}
    for journey in journeys:
        offering = by_id.get(journey.product_id or "")
        if journey.product_id and offering is None:
            raise InvalidKnowledgeError(
                f"{journey.name} is for product offering {journey.product_id!r}, which is not "
                "in the catalogue."
            )
        if offering is not None and journey.order_type_code is not None:
            codes = {item.code.casefold() for item in offering.order_types}
            if journey.order_type_code.casefold() not in codes:
                raise InvalidKnowledgeError(
                    f"{journey.name}: order type {journey.order_type_code!r} is not one of "
                    f"{offering.name}'s."
                )
        parts = {item.id for item in offering.components} if offering else set()
        for activity in journey.activities:
            for system in activity.systems:
                if system not in system_ids:
                    raise InvalidKnowledgeError(
                        f"{journey.name} › {activity.number}. {activity.name} names system "
                        f"{system!r}, which is not in the catalogue."
                    )
            unknown = [item for item in activity.component_ids if item not in parts]
            if unknown:
                raise InvalidKnowledgeError(
                    f"{journey.name} › {activity.number}. {activity.name} names component "
                    f"{unknown[0]!r}, which is not part of its product offering."
                )


def _merged_activity(first: Activity, second: Activity) -> Activity:
    return Activity(
        number=first.number,
        name=first.name,
        phase=first_known(first.phase, second.phase),
        track=first_known(first.track, second.track),
        performing_system_id=first_known(first.performing_system_id, second.performing_system_id),
        supporting_system_ids=tuple(
            dict.fromkeys((*first.supporting_system_ids, *second.supporting_system_ids))
        ),
        system_function=first_known(first.system_function, second.system_function),
        mode=first_known(first.mode, second.mode),
        customer_visible=first_known(first.customer_visible, second.customer_visible),
        description=first_known(first.description, second.description),
        component_ids=tuple(dict.fromkeys((*first.component_ids, *second.component_ids))),
        input=first_known(first.input, second.input),
        output=first_known(first.output, second.output),
        etom=first_known(first.etom, second.etom),
        confidence=first_known(first.confidence, second.confidence),
        source=first_known(first.source, second.source),
    )


def merge_journeys(first: Journey, second: Journey) -> Journey:
    """Two readings of one journey as one: the first's facts win, the second fills gaps.

    A journey section is read in parts: its activities table, the details under
    each activity, its rules and its integrations, by the table reader or a
    model. Activities merge by number, rules by kind and activities,
    integrations by their two activities.
    """
    steps = {item.number: item for item in first.activities}
    for item in second.activities:
        steps[item.number] = (
            _merged_activity(steps[item.number], item) if item.number in steps else item
        )
    rules = {(item.kind, item.from_activity, item.to_activity): item for item in first.flow_rules}
    for rule in second.flow_rules:
        rules.setdefault((rule.kind, rule.from_activity, rule.to_activity), rule)
    links = {(item.from_activity, item.to_activity): item for item in first.integrations}
    for link in second.integrations:
        links.setdefault((link.from_activity, link.to_activity), link)
    # The offering and its order type travel together: one reading's pair, gaps filled
    # only from a reading of the same offering.
    product = first.product_id or second.product_id
    order = first.order_type_code if first.product_id else second.order_type_code
    if order is None and first.product_id == second.product_id:
        order = second.order_type_code
    return Journey(
        id=first.id,
        name=first.name,
        product_id=product,
        order_type_code=order,
        description=first_known(first.description, second.description),
        activities=tuple(steps.values()),
        flow_rules=tuple(rules.values()),
        integrations=tuple(links.values()),
        confidence=first_known(first.confidence, second.confidence),
        source=first_known(first.source, second.source),
    )


def same_journey(first: Journey, second: Journey) -> bool:
    """Whether two journeys are one: the same id, or the same name for the same offering.

    A journey that does not say its offering matches one of that name that does.
    """
    if first.id == second.id:
        return True
    named = first.name.casefold().strip() == second.name.casefold().strip()
    either = first.product_id is None or second.product_id is None
    return named and (either or first.product_id == second.product_id)
