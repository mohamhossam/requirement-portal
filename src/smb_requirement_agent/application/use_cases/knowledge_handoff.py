"""Deliver approved backlogs to the knowledge service (ADR-0101 Amendment 2).

Each final approval queued a handoff. The worker leases the oldest due one, renders the
revision that approval attests as the neutral backlog export (schema 1.x) once, without
the approver's email, and delivers it to the knowledge service's change-request inbox.
The inbox is idempotent by approval, so a delivery whose answer was lost is simply sent
again. An inbox that is not there yet (404), throttles or cannot be reached is retried
with a growing pause; one that refuses the export as it is (400, 409, 413, 422) is not.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from typing import Any
from uuid import uuid4

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import ServiceResponseError, ServiceUnavailableError
from smb_requirement_agent.application.exports import ExportFormat, NeutralBacklogExport
from smb_requirement_agent.application.ports.backlog_export import BacklogExportPort
from smb_requirement_agent.application.ports.breakdown_repository import BreakdownRepositoryPort
from smb_requirement_agent.application.ports.knowledge_handoff import (
    ApprovedBacklogOutboxPort,
    BacklogHandoff,
    ChangeRequestInboxPort,
)
from smb_requirement_agent.application.use_cases.export_breakdown import (
    approved_backlog_document,
    formal_final_approval,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementId

LEASE = timedelta(minutes=5)
FIRST_RETRY = timedelta(minutes=1)
LONGEST_RETRY = timedelta(hours=1)
# About two days of hourly attempts before a handoff is left for a person.
MAX_ATTEMPTS = 48
# The inbox refused the export as it is; sending it again would be refused again.
REFUSED = frozenset({400, 409, 413, 422})

_log = logging.getLogger(__name__)


def without_email(document: NeutralBacklogExport) -> NeutralBacklogExport:
    """The export with the approver's email removed: the knowledge service keeps names only."""
    approval = document.manifest.final_approval
    return replace(
        document,
        manifest=replace(
            document.manifest,
            final_approval=replace(approval, recorded_by=replace(approval.recorded_by, email=None)),
        ),
    )


class DeliverApprovedBacklogs:
    def __init__(
        self,
        outbox: ApprovedBacklogOutboxPort,
        revisions: BreakdownRepositoryPort,
        exporter: BacklogExportPort,
        inbox: ChangeRequestInboxPort,
        clock: ClockPort,
        record: Callable[[str, float], None] | None = None,
    ) -> None:
        if exporter.format is not ExportFormat.JSON:
            raise ValueError("Approved backlogs are handed over as the JSON export.")
        self._outbox = outbox
        self._revisions = revisions
        self._exporter = exporter
        self._inbox = inbox
        self._clock = clock
        # Told each outcome (delivered, retry, skipped, failed) and how long it took.
        self._record = record

    def deliver_next(self) -> bool:
        """Work on one due handoff; False when nothing is due."""
        handoff = self._outbox.claim(self._clock.now(), LEASE, uuid4().hex)
        if handoff is None:
            return False
        started = time.monotonic()
        outcome = self._deliver(handoff)
        if self._record is not None:
            self._record(outcome, time.monotonic() - started)
        return True

    def _deliver(self, handoff: BacklogHandoff) -> str:
        payload = handoff.payload
        if payload is None:
            payload = self._render(handoff)
            if payload is None:
                self._outbox.save(
                    handoff.skipped("No exportable revision carries this approval."),
                    handoff.version,
                )
                return "skipped"
            # Kept before sending, so every retry sends the same body.
            rendered = handoff.rendered(payload)
            self._outbox.save(rendered, handoff.version)
            handoff = rendered
        try:
            change_request_id = self._inbox.deliver(payload)
        except ServiceResponseError as exc:
            if exc.status_code in REFUSED:
                _log.warning(
                    "The knowledge service refused approved backlog %s with %s.",
                    handoff.approval_id,
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
        self._outbox.save(handoff.delivered(change_request_id, self._clock.now()), handoff.version)
        return "delivered"

    def _retry(self, handoff: BacklogHandoff, reason: str) -> str:
        if handoff.attempts >= MAX_ATTEMPTS:
            _log.warning(
                "Approved backlog %s was not delivered after %s attempts.",
                handoff.approval_id,
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

    def _render(self, handoff: BacklogHandoff) -> dict[str, Any] | None:
        """The export of the first revision this approval attests, or None."""
        revisions = self._revisions.list_breakdown_revisions(RequirementId(handoff.requirement_id))
        for revision in sorted(revisions, key=lambda item: item.number.value):
            approval = formal_final_approval(revision)
            if approval is None or approval.id.value != handoff.approval_id:
                continue
            document = approved_backlog_document(revision)
            if document is None:
                return None
            export: dict[str, Any] = json.loads(self._exporter.render(without_email(document)))
            return export
        return None
