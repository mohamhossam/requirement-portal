"""Send decided product verdicts to the knowledge service (ontology plan Phase 5).

A Requirement Owner's decision on the suggested product impact is rendered, in the
decision's own transaction, as the precedent `POST /internal/architecture/precedents`
takes: the requirement's text as it was assessed, the capabilities it needed, the
offering, the systems, the suggested verdict and what the owner decided. The worker
delivers it. The knowledge service keeps the later decision on an analysis, so delivering
one again whose answer was lost changes nothing. A service that is not there yet (404),
throttles or cannot be reached is retried with a growing pause; one that refuses the
decision as it is (400, 409, 413, 422) is not.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any
from uuid import uuid4

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.use_cases.product_impact import assessed_text
from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.application.errors import ServiceResponseError, ServiceUnavailableError
from smb_requirement_agent.references.application.ports.precedent_handoff import (
    PrecedentHandoff,
    PrecedentInboxPort,
    PrecedentOutboxPort,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement

LEASE = timedelta(minutes=5)
FIRST_RETRY = timedelta(minutes=1)
LONGEST_RETRY = timedelta(hours=1)
# About two days of hourly attempts before a decision is left unsent.
MAX_ATTEMPTS = 48
# The service refused the decision as it is; sending it again would be refused again.
REFUSED = frozenset({400, 409, 413, 422})
# The contract's limits on what a precedent carries.
MAX_TEXT_PARTS = 50
MAX_TEXT_PART = 10_000
MAX_CONCEPTS = 40
MAX_SYSTEMS = 60

_log = logging.getLogger(__name__)


def precedent_handoff(
    requirement: Requirement, analysis: RequirementAnalysis
) -> PrecedentHandoff | None:
    """The decided product impact of `analysis`, ready to send; None when there is nothing
    decided to send."""
    impact = analysis.product_impact
    if analysis.id is None or impact is None or impact.decision is None:
        return None
    if impact.decided_at is None:  # pragma: no cover - a decision always records its moment
        return None
    analysis_id = analysis.id.value
    text = assessed_text(
        requirement,
        (
            *(item.statement for item in analysis.known_facts),
            *(item.statement for item in analysis.constraints),
            *(item.statement for item in analysis.business_rules),
        ),
        analysis.clarifications,
    )
    payload: dict[str, Any] = {
        "precedent_id": analysis_id,
        "requirement_id": requirement.id.value,
        "version": f"{analysis_id}@{analysis.version}",
        "release_id": impact.release_id,
        "text": [item[:MAX_TEXT_PART] for item in text[:MAX_TEXT_PARTS]],
        "decision": impact.decision.value,
        "decided_at": impact.decided_at.isoformat(),
        "suggested_verdict": impact.suggested_verdict.value if impact.suggested_verdict else None,
        "verdict": impact.verdict.value if impact.verdict else None,
        "offering_id": impact.offering_id,
        # The capabilities it needed; a weak link is a guess, so it says nothing about them.
        "concept_ids": list(
            dict.fromkeys(item.concept_id for item in impact.needs if not item.weak)
        )[:MAX_CONCEPTS],
        "systems": [
            {"id": item.id, "role": item.role, "change_type": item.change_type}
            for item in {item.id: item for item in impact.systems}.values()
        ][:MAX_SYSTEMS],
    }
    return PrecedentHandoff(
        handoff_id=f"{analysis_id}@{analysis.version}",
        requirement_id=requirement.id.value,
        payload=payload,
        created_at=impact.decided_at,
        next_attempt_at=impact.decided_at,
    )


class DeliverPrecedents:
    def __init__(
        self,
        outbox: PrecedentOutboxPort,
        inbox: PrecedentInboxPort,
        clock: ClockPort,
        record: Callable[[str, float], None] | None = None,
    ) -> None:
        self._outbox = outbox
        self._inbox = inbox
        self._clock = clock
        # Told each outcome (delivered, retry, failed) and how long it took.
        self._record = record

    def deliver_next(self) -> bool:
        """Work on one due decision; False when nothing is due."""
        handoff = self._outbox.claim(self._clock.now(), LEASE, uuid4().hex)
        if handoff is None:
            return False
        started = time.monotonic()
        outcome = self._deliver(handoff)
        if self._record is not None:
            self._record(outcome, time.monotonic() - started)
        return True

    def _deliver(self, handoff: PrecedentHandoff) -> str:
        try:
            self._inbox.record(handoff.payload)
        except ServiceResponseError as exc:
            if exc.status_code in REFUSED:
                _log.warning(
                    "The knowledge service refused decided verdict %s with %s.",
                    handoff.handoff_id,
                    exc.status_code,
                )
                self._outbox.save(
                    handoff.failed(f"The knowledge service refused it ({exc.status_code})."),
                    handoff.version,
                )
                return "failed"
            return self._retry(handoff, f"The knowledge service answered {exc.status_code}.")
        except ServiceUnavailableError:
            return self._retry(handoff, "The knowledge service could not be reached.")
        self._outbox.save(handoff.delivered(self._clock.now()), handoff.version)
        return "delivered"

    def _retry(self, handoff: PrecedentHandoff, reason: str) -> str:
        if handoff.attempts >= MAX_ATTEMPTS:
            _log.warning(
                "Decided verdict %s was not delivered after %s attempts.",
                handoff.handoff_id,
                handoff.attempts,
            )
            self._outbox.save(
                handoff.failed(f"{reason} Gave up after {handoff.attempts} attempts."),
                handoff.version,
            )
            return "failed"
        pause = min(LONGEST_RETRY, FIRST_RETRY * 2 ** max(handoff.attempts - 1, 0))
        self._outbox.save(handoff.retried(reason, self._clock.now() + pause), handoff.version)
        return "retry"
