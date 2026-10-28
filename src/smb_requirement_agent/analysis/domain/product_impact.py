"""A requirement's product impact, decided in analysis (ADR-0115).

The knowledge portal suggests where a requirement sits in the product portfolio: a
verdict, the offering it changes, the capability concepts it needs and the systems that
realise them. A person then accepts the suggestion, overrides the verdict, or marks it
unknown. Generation and publication read only the decision (ADR-0116).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import Any

from smb_requirement_agent.analysis.domain.errors import InvalidProductImpactDecisionError
from smb_requirement_agent.shared_kernel.actors import ActorProfile, ActorSnapshot
from smb_requirement_agent.shared_kernel.staleness import require_aware


class ProductVerdict(StrEnum):
    """The knowledge portal's four answers to "is this an existing product or a new one?"."""

    CHANGE_EXISTING_OFFERING = "change_existing_offering"
    NEW_PLAN = "new_plan"
    NEW_OFFERING_IN_FAMILY = "new_offering_in_family"
    NEW_PRODUCT_LINE = "new_product_line"

    @property
    def names_an_offering(self) -> bool:
        """Only a change to an offering, or a new plan of one, has an offering to name."""
        return self in (ProductVerdict.CHANGE_EXISTING_OFFERING, ProductVerdict.NEW_PLAN)


class ProductImpactDecision(StrEnum):
    ACCEPTED = "accepted"
    OVERRIDDEN = "overridden"
    UNKNOWN = "unknown"


class ProductImpactStatus(StrEnum):
    """Whether an analysis round could ask the knowledge portal for a product impact."""

    ASSESSED = "assessed"
    NOT_CONNECTED = "not_connected"
    UNAVAILABLE = "unavailable"


def _text(value: str, field: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise InvalidProductImpactDecisionError(f"{field} cannot be empty.")
    return stripped


@dataclass(frozen=True)
class ImpactPathStep:
    """One hop from the requirement to a system: a facet, a concept, an offering, ..."""

    kind: str
    id: str
    label: str


@dataclass(frozen=True)
class CapabilityNeed:
    """A capability concept the requirement needs, and whether the offering covers it."""

    concept_id: str
    label: str
    path: str
    covered: bool
    weak: bool = False


@dataclass(frozen=True)
class ImpactGap:
    """A capability realised nowhere, or a system with no one to change it."""

    kind: str
    concept_id: str
    label: str
    reason: str
    system_id: str | None = None


@dataclass(frozen=True)
class ImpactSystem:
    id: str
    name: str
    role: str
    change_type: str
    paths: tuple[tuple[ImpactPathStep, ...], ...] = ()


@dataclass(frozen=True)
class ImpactOwner:
    """Who changes a system for one capability: its squads and the people seated on it."""

    concept_id: str
    system_id: str
    squads: tuple[str, ...] = ()
    people: tuple[str, ...] = ()
    open_seats: int = 0


@dataclass(frozen=True)
class ImpactQuestion:
    """What the knowledge portal needs to know before it can place the requirement."""

    facet: str
    question: str
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class DraftComponent:
    """A component of a drafted offering, and the systems that would deliver it."""

    name: str
    system_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class OfferingDraft:
    """The offering and journey the knowledge portal drafted for a new-offering verdict.

    A proposal for the catalogue's curators, never a decision here (ontology plan Phase 9):
    `document` is the draft as the knowledge portal wrote it, sent back unchanged with the
    approved backlog, where a curator edits and accepts it. The other fields are what this
    application shows of it.
    """

    offering_id: str
    offering_name: str
    components: tuple[DraftComponent, ...] = ()
    # The questions it leaves for architecture review, such as which system will realise a
    # capability no system realises yet.
    questions: tuple[str, ...] = ()
    journey_name: str | None = None
    journey_steps: int = 0
    # The offering it was drafted from, if any.
    based_on: str | None = None
    document: dict[str, Any] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "offering_id", _text(self.offering_id, "Drafted offering id"))
        object.__setattr__(
            self, "offering_name", _text(self.offering_name, "Drafted offering name")
        )
        if self.journey_steps < 0:
            raise InvalidProductImpactDecisionError(
                "A drafted journey's step count cannot be negative."
            )


@dataclass(frozen=True)
class ProductImpact:
    """The knowledge portal's suggestion for one analysis round, and a person's decision."""

    release_id: str
    suggested_verdict: ProductVerdict | None
    reason: str
    assessed_at: datetime
    offering_id: str | None = None
    offering_name: str | None = None
    proposal: str | None = None
    new_values: tuple[str, ...] = ()
    # For a new offering in a family or a new product line (ontology plan Phase 9).
    draft: OfferingDraft | None = None
    needs: tuple[CapabilityNeed, ...] = ()
    # The need phrases the portal read in the requirement, which a decided precedent is
    # compared by; none for an impact assessed before they were kept.
    need_texts: tuple[str, ...] = ()
    gaps: tuple[ImpactGap, ...] = ()
    systems: tuple[ImpactSystem, ...] = ()
    owners: tuple[ImpactOwner, ...] = ()
    questions: tuple[ImpactQuestion, ...] = ()
    uncertainty: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    decision: ProductImpactDecision | None = None
    # The verdict a person decided: the suggestion when accepted, their own when overridden,
    # none when they marked it unknown.
    verdict: ProductVerdict | None = None
    rationale: str | None = None
    decided_by: ActorSnapshot | None = None
    decided_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "release_id", _text(self.release_id, "Catalogue release"))
        object.__setattr__(self, "reason", self.reason.strip())
        require_aware(self.assessed_at, "product impact assessed_at")
        if self.rationale is not None:
            object.__setattr__(self, "rationale", self.rationale.strip() or None)
        if (self.decided_by is None) != (self.decided_at is None) or (self.decided_by is None) != (
            self.decision is None
        ):
            raise InvalidProductImpactDecisionError(
                "A product impact decision, its author and its time go together."
            )
        if self.decided_at is not None:
            require_aware(self.decided_at, "product impact decided_at")
        if self.decision is None and self.verdict is not None:
            raise InvalidProductImpactDecisionError("Only a decided impact has a verdict.")
        if self.decision is ProductImpactDecision.ACCEPTED and (
            self.suggested_verdict is None or self.verdict is not self.suggested_verdict
        ):
            raise InvalidProductImpactDecisionError(
                "Only a suggested verdict can be accepted, and it stays as suggested."
            )
        if self.decision is ProductImpactDecision.OVERRIDDEN and (
            self.verdict is None or self.verdict is self.suggested_verdict
        ):
            raise InvalidProductImpactDecisionError(
                "An override chooses a verdict other than the suggested one."
            )
        if self.decision is ProductImpactDecision.OVERRIDDEN and self.rationale is None:
            raise InvalidProductImpactDecisionError("Say why the suggested verdict is wrong.")
        if self.decision is ProductImpactDecision.UNKNOWN and self.verdict is not None:
            raise InvalidProductImpactDecisionError("An unknown impact has no verdict.")

    @property
    def is_decided(self) -> bool:
        return self.decision is not None

    @property
    def decided_offering_id(self) -> str | None:
        """The offering the decided verdict changes, when it names one."""
        if self.verdict is None or not self.verdict.names_an_offering:
            return None
        return self.offering_id

    @property
    def decided_draft(self) -> OfferingDraft | None:
        """The drafted offering, while the decided verdict is still a new offering."""
        if self.verdict is None or self.verdict.names_an_offering:
            return None
        return self.draft

    @property
    def covered_needs(self) -> tuple[CapabilityNeed, ...]:
        return tuple(item for item in self.needs if item.covered)

    @property
    def capability_gaps(self) -> tuple[ImpactGap, ...]:
        return tuple(item for item in self.gaps if item.kind == "capability")

    @property
    def weak_needs(self) -> tuple[CapabilityNeed, ...]:
        return tuple(item for item in self.needs if item.weak)

    def decide(
        self,
        decision: ProductImpactDecision,
        actor: ActorProfile,
        at: datetime,
        *,
        verdict: ProductVerdict | None = None,
        rationale: str | None = None,
    ) -> ProductImpact:
        if decision is ProductImpactDecision.ACCEPTED:
            if self.suggested_verdict is None:
                raise InvalidProductImpactDecisionError(
                    "There is no suggested verdict to accept: answer the open questions, "
                    "choose a verdict, or mark it unknown."
                )
            verdict = self.suggested_verdict
        elif decision is ProductImpactDecision.OVERRIDDEN:
            if verdict is None:
                raise InvalidProductImpactDecisionError("Choose the verdict that applies.")
            if verdict is self.suggested_verdict:
                raise InvalidProductImpactDecisionError(
                    "That is the suggested verdict: accept it instead."
                )
        else:
            verdict = None
        return replace(
            self,
            decision=decision,
            verdict=verdict,
            rationale=rationale,
            decided_by=actor.snapshot(),
            decided_at=require_aware(at, "product impact decided_at"),
        )

    def carried_from(self, previous: ProductImpact | None) -> ProductImpact:
        """Keep an earlier decision while the suggestion it decided on still stands.

        A new round re-asks the knowledge portal. When its suggested verdict and offering
        are those the person decided on, their decision still applies; otherwise they
        decide again.
        """
        if (
            previous is None
            or previous.decision is None
            or self.decision is not None
            or (self.suggested_verdict, self.offering_id)
            != (previous.suggested_verdict, previous.offering_id)
        ):
            return self
        return replace(
            self,
            decision=previous.decision,
            verdict=previous.verdict,
            rationale=previous.rationale,
            decided_by=previous.decided_by,
            decided_at=previous.decided_at,
        )
