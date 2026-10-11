"""Tell the knowledge service what a closed Epic delivered (ontology plan Phase 7).

The work-item tracker's service hook reports a work item's new state. An event on an Epic
this portal published, closed as done or removed, is queued once by its event id. The
worker then reads the Epic's Features' states in the tracker, and renders, once, what the
published revision promised beside what was delivered: the Features closed as done and the
systems their mappings name, the systems the decided product impact predicted, and the
catalogue changes that impact implies for what was delivered. It delivers that to the
knowledge service's `POST /internal/change-requests/deliveries`, which keeps it as a
catalogue change for a knowledge admin to read. A removed Epic is sent too, so a closure
still waiting there is withdrawn.

Which catalogue changes: each capability the requirement needed that the catalogue did not
cover (a weak link is a guess, so it is left out). A delivered system the assessment reached
through that capability realises it now; when the verdict changes an existing offering, the
offering is asked which of its components delivers it. With no such system, the offering is
asked only when the whole Epic was delivered.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.domain.product_impact import ProductImpact, ProductVerdict
from smb_requirement_agent.application.errors import ServiceResponseError, ServiceUnavailableError
from smb_requirement_agent.governance.application.errors import (
    PublicationTargetError,
    PublicationUnavailableError,
)
from smb_requirement_agent.governance.application.exports import (
    ExportArchitecture,
    ExportFeature,
    NeutralBacklogExport,
)
from smb_requirement_agent.governance.application.ports.backlog_publisher import (
    BacklogPublisherPort,
)
from smb_requirement_agent.governance.application.ports.breakdown_repository import (
    BreakdownRepositoryPort,
)
from smb_requirement_agent.governance.application.ports.publication_repository import (
    PublicationRepositoryPort,
)
from smb_requirement_agent.governance.application.publication import WorkItemKind
from smb_requirement_agent.governance.application.use_cases.export_breakdown import (
    approved_backlog_document,
)
from smb_requirement_agent.governance.domain.publication.entities import BacklogPublication
from smb_requirement_agent.governance.domain.revision.entities import RevisionNumber
from smb_requirement_agent.references.application.ports.delivery_closure import (
    DeliveryClosure,
    DeliveryClosureOutboxPort,
    DeliveryInboxPort,
    EpicOutcome,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

LEASE = timedelta(minutes=5)
FIRST_RETRY = timedelta(minutes=1)
LONGEST_RETRY = timedelta(hours=1)
# About two days of hourly attempts before a closure is left unsent.
MAX_ATTEMPTS = 48
# The service refused the closure as it is; sending it again would be refused again.
REFUSED = frozenset({400, 409, 413, 422})
# Tracker states, compared case aside. Done is Scrum's; Closed is Agile's and CMMI's.
DELIVERED_STATES = frozenset({"closed", "done"})
REMOVED_STATES = frozenset({"removed"})
# Verdicts that keep the offering the assessment named, so it can be asked about.
OFFERING_KEPT = frozenset({ProductVerdict.CHANGE_EXISTING_OFFERING, ProductVerdict.NEW_PLAN})
# The contract's limits.
MAX_ITEMS = 5_000

_log = logging.getLogger(__name__)


def epic_outcome(state: str) -> EpicOutcome | None:
    """What a tracker state means for an Epic: closed as done, removed, or neither."""
    key = state.strip().casefold()
    if key in DELIVERED_STATES:
        return EpicOutcome.CLOSED
    if key in REMOVED_STATES:
        return EpicOutcome.REMOVED
    return None


@dataclass(frozen=True)
class TrackerEvent:
    """A work item's new state, as the tracker's service hook reports it."""

    event_id: str
    work_item_id: str
    state: str
    occurred_at: datetime


class RecordTrackerEvent:
    """Behind the tracker's service hook: queue an event on a published Epic, once."""

    def __init__(
        self,
        publications: PublicationRepositoryPort,
        outbox: DeliveryClosureOutboxPort,
        clock: ClockPort,
    ) -> None:
        self._publications = publications
        self._outbox = outbox
        self._clock = clock

    def execute(self, event: TrackerEvent) -> DeliveryClosure | None:
        """The closure queued for this event, or None when it says nothing to send: another
        state, or a work item that is not an Epic this portal published."""
        outcome = epic_outcome(event.state)
        if outcome is None:
            return None
        record = self._publications.find_by_work_item(WorkItemKind.EPIC.value, event.work_item_id)
        if record is None:
            return None
        now = self._clock.now()
        requirement_id = record.requirement_id.value
        closure = DeliveryClosure(
            closure_id=f"{requirement_id}:{event.work_item_id}:{event.event_id}",
            requirement_id=requirement_id,
            epic_external_id=event.work_item_id,
            outcome=outcome,
            occurred_at=event.occurred_at,
            created_at=now,
            next_attempt_at=now,
        )
        self._outbox.enqueue(closure)
        return closure


@dataclass(frozen=True)
class _Feature:
    feature: ExportFeature
    external_id: str | None
    state: str
    delivered: bool
    # The systems its mapping and its Stories' name, by id or name, each once.
    systems: tuple[tuple[str | None, str], ...]


def _systems(feature: ExportFeature) -> tuple[tuple[str | None, str], ...]:
    blocks: list[ExportArchitecture | None] = [
        feature.architecture,
        *(story.architecture for story in feature.stories),
    ]
    found: dict[str, tuple[str | None, str]] = {}
    for block in blocks:
        for system in block.systems if block is not None else ():
            # The export names a system the catalogue lacks by name only.
            identifier = system.id if system.catalogued else None
            found.setdefault((identifier or system.name).casefold(), (identifier, system.name))
    return tuple(found.values())


def _changes(impact: ProductImpact, features: list[_Feature], whole: bool) -> list[dict[str, Any]]:
    delivered = [item for item in features if item.delivered]
    by_system: dict[str, list[str]] = {}
    for item in delivered:
        for identifier, name in item.systems:
            by_system.setdefault((identifier or name).casefold(), []).append(item.feature.id)
    offering = (
        impact.offering_id
        if impact.verdict in OFFERING_KEPT and impact.offering_id is not None
        else None
    )
    changes: list[dict[str, Any]] = []
    for need in dict((item.concept_id, item) for item in impact.needs).values():
        if need.covered or need.weak:
            continue
        concept = need.concept_id
        tied = [
            system
            for system in impact.systems
            if system.id.casefold() in by_system
            and any(
                step.kind == "concept" and step.id == concept
                for path in system.paths
                for step in path
            )
        ]
        if not tied:
            tied = [
                system
                for gap in impact.gaps
                if gap.concept_id == concept and gap.system_id
                for system in impact.systems
                if system.id == gap.system_id and system.id.casefold() in by_system
            ]
        tied = list({system.id: system for system in tied}.values())
        if not tied and not whole:
            # Part of the Epic was dropped and nothing ties this need to what shipped.
            continue
        feature_ids = (
            list(
                dict.fromkeys(
                    feature for system in tied for feature in by_system[system.id.casefold()]
                )
            )
            if tied
            else [item.feature.id for item in delivered]
        )
        for system in tied:
            changes.append(
                {
                    "op": "realise_concept",
                    "concept_id": concept,
                    "concept_label": need.label,
                    "system_id": system.id,
                    "system_name": system.name,
                    "feature_ids": by_system[system.id.casefold()],
                }
            )
        if offering is not None:
            changes.append(
                {
                    "op": "offer_concept",
                    "concept_id": concept,
                    "concept_label": need.label,
                    "offering_id": offering,
                    "offering_name": impact.offering_name,
                    "feature_ids": feature_ids,
                }
            )
    return changes[:MAX_ITEMS]


def delivery_body(
    closure: DeliveryClosure,
    record: BacklogPublication,
    document: NeutralBacklogExport,
    impact: ProductImpact | None,
    impact_version: str | None,
    states: dict[str, str],
) -> dict[str, Any]:
    """What `POST /internal/change-requests/deliveries` takes for this closure.

    A closure without a decided product impact carries no comparison; the caller skips it.
    """
    epic = document.epic
    mapping = record.mapping_for(epic.id)
    body: dict[str, Any] = {
        "delivery_id": closure.closure_id,
        "state": closure.outcome.value,
        "requirement_id": closure.requirement_id,
        "breakdown_revision": document.manifest.breakdown_revision,
        "approval_id": document.manifest.final_approval.id,
        "epic": {
            "id": epic.id,
            "name": epic.name,
            "external_id": closure.epic_external_id,
            "url": mapping.url if mapping is not None else None,
        },
        "occurred_at": closure.occurred_at.isoformat(),
    }
    if closure.outcome is EpicOutcome.REMOVED or impact is None or impact_version is None:
        return body
    features: list[_Feature] = []
    for feature in epic.features:
        published = record.mapping_for(feature.id)
        external_id = published.external_id if published is not None else None
        state = states.get(external_id, "Unknown") if external_id is not None else "Unpublished"
        features.append(
            _Feature(
                feature,
                external_id,
                state,
                state.strip().casefold() in DELIVERED_STATES,
                _systems(feature),
            )
        )
    whole = all(item.delivered for item in features)
    return {
        **body,
        "release_id": impact.release_id,
        "impact_version": impact_version,
        "decision": impact.decision.value if impact.decision else None,
        "suggested_verdict": impact.suggested_verdict.value if impact.suggested_verdict else None,
        "verdict": impact.verdict.value if impact.verdict else None,
        "offering_id": impact.offering_id,
        "offering_name": impact.offering_name,
        "predicted_systems": [
            {"id": item.id, "name": item.name, "role": item.role, "change_type": item.change_type}
            for item in {item.id: item for item in impact.systems}.values()
        ][:MAX_ITEMS],
        "features": [
            {
                "id": item.feature.id,
                "sequence": item.feature.sequence,
                "name": item.feature.name,
                "outcome": item.feature.outcome or None,
                "external_id": item.external_id,
                "state": item.state,
                "delivered": item.delivered,
                "systems": [{"id": identifier, "name": name} for identifier, name in item.systems],
            }
            for item in features
        ],
        "changes": _changes(impact, features, whole),
    }


class DeliverClosures:
    def __init__(
        self,
        outbox: DeliveryClosureOutboxPort,
        publications: PublicationRepositoryPort,
        revisions: BreakdownRepositoryPort,
        publisher: BacklogPublisherPort,
        inbox: DeliveryInboxPort,
        clock: ClockPort,
        record: Callable[[str, float], None] | None = None,
    ) -> None:
        self._outbox = outbox
        self._publications = publications
        self._revisions = revisions
        self._publisher = publisher
        self._inbox = inbox
        self._clock = clock
        # Told each outcome (delivered, retry, skipped, failed) and how long it took.
        self._record = record

    def deliver_next(self) -> bool:
        """Work on one due closure; False when nothing is due."""
        closure = self._outbox.claim(self._clock.now(), LEASE, uuid4().hex)
        if closure is None:
            return False
        started = time.monotonic()
        outcome = self._deliver(closure)
        if self._record is not None:
            self._record(outcome, time.monotonic() - started)
        return True

    def _deliver(self, closure: DeliveryClosure) -> str:
        payload = closure.payload
        if payload is None:
            try:
                rendered, skipped = self._render(closure)
            except (PublicationTargetError, PublicationUnavailableError) as exc:
                return self._retry(closure, f"The work-item tracker did not answer: {exc}")
            if rendered is None:
                self._outbox.save(closure.skipped(skipped), closure.version)
                return "skipped"
            # Kept before sending, so every retry sends the same body.
            kept = closure.rendered(rendered)
            self._outbox.save(kept, closure.version)
            closure, payload = kept, rendered
        try:
            receipt = self._inbox.deliver(payload)
        except ServiceResponseError as exc:
            if exc.status_code in REFUSED:
                _log.warning(
                    "The knowledge service refused delivery %s with %s.",
                    closure.closure_id,
                    exc.status_code,
                )
                self._outbox.save(
                    closure.failed(f"The knowledge service refused it ({exc.status_code})."),
                    closure.version,
                )
                return "failed"
            return self._retry(closure, f"The knowledge service answered {exc.status_code}.")
        except ServiceUnavailableError:
            return self._retry(closure, "The knowledge service could not be reached.")
        self._outbox.save(
            closure.delivered(receipt.change_request_id, self._clock.now()), closure.version
        )
        return "delivered"

    def _render(self, closure: DeliveryClosure) -> tuple[dict[str, Any] | None, str]:
        """The body to send, or None and why there is nothing to send."""
        requirement = RequirementId(closure.requirement_id)
        record = self._publications.get(requirement)
        number = record.published_revision() if record is not None else None
        if record is None or number is None:
            return None, "The Requirement has no published revision."
        if record.target_key != self._publisher.target().key:
            return None, "The Epic was published to another tracker than the one set up now."
        revision = self._revisions.get_breakdown_revision(requirement, RevisionNumber(number))
        document = approved_backlog_document(revision) if revision is not None else None
        if revision is None or document is None:
            return None, "The published revision is no longer exportable."
        analysis = revision.analysis
        impact = analysis.product_impact if analysis is not None else None
        if closure.outcome is EpicOutcome.REMOVED:
            return delivery_body(closure, record, document, None, None, {}), ""
        if analysis is None or analysis.id is None or impact is None or impact.decision is None:
            return None, "No product impact was decided for the published revision."
        ids = tuple(
            mapping.external_id
            for feature in document.epic.features
            if (mapping := record.mapping_for(feature.id)) is not None
        )
        states = self._publisher.states(ids)
        body = delivery_body(
            closure, record, document, impact, f"{analysis.id.value}@{analysis.version}", states
        )
        if not any(item["delivered"] for item in body["features"]):
            return None, "No Feature of the Epic was closed as done."
        return body, ""

    def _retry(self, closure: DeliveryClosure, reason: str) -> str:
        if closure.attempts >= MAX_ATTEMPTS:
            _log.warning(
                "Delivery %s was not sent after %s attempts.",
                closure.closure_id,
                closure.attempts,
            )
            self._outbox.save(
                closure.failed(f"{reason} Gave up after {closure.attempts} attempts."),
                closure.version,
            )
            return "failed"
        pause = min(LONGEST_RETRY, FIRST_RETRY * 2 ** max(closure.attempts - 1, 0))
        self._outbox.save(closure.retried(reason, self._clock.now() + pause), closure.version)
        return "retry"
