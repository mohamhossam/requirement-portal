"""Product offerings and journeys around an impact, for a reviewer (ADR-0097).

Two notes, read from the pinned release and never mapping a system:
- the product offerings the item's text names, by the offering's own name or
  code, or a component's, with the systems responsible for what it named;
- the journey activities each mapped system performs or supports, with the
  activities just before and after, so a reviewer sees who hands over to and
  from the change.

Words match as whole phrases, the way capability domains do (ADR-0089).
"""

from __future__ import annotations

from smb_requirement_agent.application.use_cases.capability_domain_fallback import (
    contains,
    normalise,
)
from smb_requirement_agent.domain.architecture.entities import (
    JourneyNeighbour,
    JourneyStep,
    OfferingDuty,
    ProductContext,
)
from smb_requirement_agent.domain.architecture.journeys import Activity, Journey, journey_edges
from smb_requirement_agent.domain.architecture.knowledge import ArchitectureKnowledge
from smb_requirement_agent.domain.architecture.products import OrderType, ProductOffering

MAX_PRODUCT_CONTEXTS = 2
MAX_JOURNEY_STEPS = 12


def _matched(corpus: str, *terms: str | None) -> tuple[str, ...]:
    """The terms the corpus holds, each once however it is written ("BPP_PLUS" is "BPP Plus")."""
    found: dict[str, str] = {}
    for term in terms:
        if term and contains(corpus, term):
            found.setdefault(normalise(term), term)
    return tuple(found.values())


def _order_type(corpus: str, offering: ProductOffering) -> OrderType | None:
    return next(
        (item for item in offering.order_types if _matched(corpus, item.name, item.code)), None
    )


def product_contexts(release: ArchitectureKnowledge, text: str) -> tuple[ProductContext, ...]:
    """The offerings the text names, by their name or code or a component's, most named first.

    The responsibilities are those of the components it named, or all of the
    offering's when it named none, kept to the order type it named when a
    responsibility says which order types it serves.
    """
    corpus = normalise(text)
    if not corpus:
        return ()
    names = {system.id: system.name for system in release.systems}
    ranked: list[tuple[int, int, str, ProductContext]] = []
    for offering in release.products:
        own = _matched(corpus, offering.name, offering.code)
        parts = [
            (part, words)
            for part in offering.components
            if (words := _matched(corpus, part.name, part.code))
        ]
        if not own and not parts:
            continue
        order = _order_type(corpus, offering)
        chosen = [part for part, _ in parts] or list(offering.components)
        duties = tuple(
            OfferingDuty(
                part.id,
                part.name,
                duty.system_id,
                names.get(duty.system_id, duty.system_id),
                duty.role,
                duty.description,
            )
            for part in chosen
            for duty in part.responsibilities
            if order is None or not duty.order_types or order.code in duty.order_types
        )
        matched = (
            *own,
            *(word for _, words in parts for word in words),
            *(_matched(corpus, order.name, order.code) if order else ()),
        )
        context = ProductContext(
            offering.id,
            offering.name,
            tuple(dict.fromkeys(matched)),
            order.name if order else None,
            duties,
        )
        ranked.append((-len(own), -len(matched), offering.name, context))
    ranked.sort(key=lambda item: item[:3])
    return tuple(item[3] for item in ranked[:MAX_PRODUCT_CONTEXTS])


def _neighbour(activity: Activity, names: dict[str, str]) -> JourneyNeighbour:
    system = activity.performing_system_id
    return JourneyNeighbour(
        activity.number,
        activity.name,
        system,
        names.get(system, system) if system else None,
    )


def _focused(
    release: ArchitectureKnowledge, contexts: tuple[ProductContext, ...]
) -> tuple[Journey, ...]:
    """The journeys worth showing: of the offerings the item names, and of the order type it
    names when one of them fulfils it; every journey when it names no offering."""
    if not contexts:
        return release.journeys
    offerings = {item.product_id for item in contexts}
    of_offering = [item for item in release.journeys if item.product_id in offerings]
    by_id = {item.id: item for item in release.products}
    named = set()
    for context in contexts:
        offering = by_id.get(context.product_id)
        for order in offering.order_types if offering else ():
            if order.name == context.order_type:
                named.add((context.product_id, order.code))
    of_order = [item for item in of_offering if (item.product_id, item.order_type_code) in named]
    return tuple(of_order or of_offering)


def journey_steps(
    release: ArchitectureKnowledge,
    mapped: set[str],
    contexts: tuple[ProductContext, ...] = (),
) -> tuple[JourneyStep, ...]:
    """Each journey activity a mapped system performs or supports, in journey order.

    Before and after are the activities the derived flow (ADR-0096) leads in
    from and out to. At most ``MAX_JOURNEY_STEPS``, journeys of the offering the
    item names first.
    """
    if not mapped:
        return ()
    names = {system.id: system.name for system in release.systems}
    offerings = {item.id: item for item in release.products}
    steps: list[JourneyStep] = []
    for journey in _focused(release, contexts):
        offering = offerings.get(journey.product_id or "")
        order = next(
            (
                item.name
                for item in (offering.order_types if offering else ())
                if item.code == journey.order_type_code
            ),
            journey.order_type_code,
        )
        fulfils = tuple(item for item in (offering.name if offering else None, order) if item)
        activities = {item.number: item for item in journey.activities}
        edges = journey_edges(journey)
        for activity in journey.ordered:
            for system_id in (item for item in activity.systems if item in mapped):
                before = tuple(
                    _neighbour(activities[edge.from_activity], names)
                    for edge in edges
                    if edge.to_activity == activity.number
                )
                after = tuple(
                    _neighbour(activities[edge.to_activity], names)
                    for edge in edges
                    if edge.from_activity == activity.number
                )
                steps.append(
                    JourneyStep(
                        system_id,
                        journey.id,
                        journey.name,
                        activity.number,
                        activity.name,
                        system_id == activity.performing_system_id,
                        fulfils,
                        before,
                        after,
                    )
                )
                if len(steps) == MAX_JOURNEY_STEPS:
                    return tuple(steps)
    return tuple(steps)
