"""The publication record of one Requirement's backlog in a work-item tracker (Slice 13).

External ids live here, never on Epic, Feature or Story (AGENTS.md §9). A record keeps which
local item became which tracker item, with the content it was last sent, and every attempt
with its result per item, so republishing updates what exists instead of duplicating it.

It also keeps the Requirement's accepted product verdict and that verdict's version, so a
delivery closing in the tracker can be traced to what was promised (the ontology and impact
implementation plan, Phase 7). Requirement analysis does not decide a verdict yet (Phase 4),
so both stay empty until it does.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from smb_requirement_agent.governance.domain.publication.errors import (
    InvalidPublicationError,
    PublicationInProgressError,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.staleness import require_aware


class ItemResult(StrEnum):
    """What one attempt did with one backlog item."""

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    # Created by an interrupted attempt, found again in the tracker, and brought up to date.
    RECOVERED = "recovered"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"


SUCCEEDED = frozenset(
    {ItemResult.CREATED, ItemResult.UPDATED, ItemResult.UNCHANGED, ItemResult.RECOVERED}
)


class PublicationOutcome(StrEnum):
    PUBLISHED = "published"
    # Some items were sent before one was refused; they stay in the tracker.
    PARTIAL = "partial"
    FAILED = "failed"
    # The attempt stopped without finishing, such as when its process ended.
    INTERRUPTED = "interrupted"


class PublicationStatus(StrEnum):
    NOT_PUBLISHED = "not_published"
    IN_PROGRESS = "in_progress"
    PUBLISHED = "published"
    # The last attempt did not send everything; a retry continues it.
    INCOMPLETE = "incomplete"
    # A newer revision has final approval and has not been published.
    OUTDATED = "outdated"


@dataclass(frozen=True)
class ExternalWorkItemMapping:
    """One local item and the tracker item it became."""

    local_key: str
    kind: str
    external_id: str
    url: str
    # The content last sent, so an unchanged item is not sent again.
    content_fingerprint: str
    revision: int
    published_at: datetime

    def __post_init__(self) -> None:
        for name in ("local_key", "kind", "external_id", "url", "content_fingerprint"):
            if not getattr(self, name).strip():
                raise InvalidPublicationError(f"A work-item mapping needs a {name}.")
        if self.revision < 1:
            raise InvalidPublicationError("A work-item mapping names a positive revision.")
        require_aware(self.published_at, "mapping published_at")


@dataclass(frozen=True)
class ItemOutcome:
    local_key: str
    result: ItemResult
    error: str | None = None


@dataclass(frozen=True)
class PublicationResult:
    """One attempt to publish one revision, and what happened to each item."""

    number: int
    revision: int
    actor_id: str
    actor_name: str
    started_at: datetime
    lease_until: datetime
    items: tuple[ItemOutcome, ...] = ()
    finished_at: datetime | None = None
    interrupted: bool = False

    def __post_init__(self) -> None:
        if self.number < 1 or self.revision < 1:
            raise InvalidPublicationError("An attempt has a positive number and revision.")
        require_aware(self.started_at, "attempt started_at")
        require_aware(self.lease_until, "attempt lease_until")
        if self.finished_at is not None:
            require_aware(self.finished_at, "attempt finished_at")
        keys = [item.local_key for item in self.items]
        if len(keys) != len(set(keys)):
            raise InvalidPublicationError("An attempt reports each item once.")

    @property
    def running(self) -> bool:
        return self.finished_at is None

    @property
    def outcome(self) -> PublicationOutcome | None:
        if self.running:
            return None
        if self.interrupted:
            return PublicationOutcome.INTERRUPTED
        if all(item.result in SUCCEEDED for item in self.items):
            return PublicationOutcome.PUBLISHED
        if any(item.result in SUCCEEDED for item in self.items):
            return PublicationOutcome.PARTIAL
        return PublicationOutcome.FAILED


@dataclass(frozen=True)
class BacklogPublication:
    requirement_id: RequirementId
    # Which tracker and project the mappings belong to, as the publisher names it.
    target_key: str
    version: int = 1
    mappings: tuple[ExternalWorkItemMapping, ...] = ()
    results: tuple[PublicationResult, ...] = ()
    product_verdict: str | None = None
    product_impact_version: str | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise InvalidPublicationError("A publication record version starts at 1.")
        if not self.target_key.strip():
            raise InvalidPublicationError("A publication record names its target.")
        keys = [item.local_key for item in self.mappings]
        if len(keys) != len(set(keys)):
            raise InvalidPublicationError("Each local item maps to one tracker item.")
        ids = [item.external_id for item in self.mappings]
        if len(ids) != len(set(ids)):
            raise InvalidPublicationError("Each tracker item maps to one local item.")
        numbers = [item.number for item in self.results]
        if numbers != list(range(1, len(numbers) + 1)):
            raise InvalidPublicationError("Attempts are numbered from 1 in order.")
        if any(item.running for item in self.results[:-1]):
            raise InvalidPublicationError("Only the latest attempt can still be running.")
        if (self.product_verdict is None) != (self.product_impact_version is None):
            raise InvalidPublicationError("A product verdict is kept with its version.")

    @property
    def latest(self) -> PublicationResult | None:
        return self.results[-1] if self.results else None

    def mapping_for(self, local_key: str) -> ExternalWorkItemMapping | None:
        return next((item for item in self.mappings if item.local_key == local_key), None)

    def published_revision(self) -> int | None:
        """The revision the latest finished, complete attempt published."""
        return next(
            (
                item.revision
                for item in reversed(self.results)
                if item.outcome is PublicationOutcome.PUBLISHED
            ),
            None,
        )

    def status(self, latest_approved_revision: int | None, now: datetime) -> PublicationStatus:
        latest = self.latest
        if latest is None:
            return PublicationStatus.NOT_PUBLISHED
        if latest.running and latest.lease_until > now:
            return PublicationStatus.IN_PROGRESS
        if latest.running or latest.outcome is not PublicationOutcome.PUBLISHED:
            return PublicationStatus.INCOMPLETE
        if latest_approved_revision is not None and latest_approved_revision > latest.revision:
            return PublicationStatus.OUTDATED
        return PublicationStatus.PUBLISHED

    def start(
        self, revision: int, actor_id: str, actor_name: str, now: datetime, lease_until: datetime
    ) -> BacklogPublication:
        """Begin an attempt. One whose lease ran out is closed as interrupted first."""
        require_aware(now, "attempt start")
        results = self.results
        latest = self.latest
        if latest is not None and latest.running:
            if latest.lease_until > now:
                raise PublicationInProgressError(
                    "This backlog is being published already; wait for it to finish."
                )
            results = (*results[:-1], replace(latest, finished_at=now, interrupted=True))
        attempt = PublicationResult(
            number=len(results) + 1,
            revision=revision,
            actor_id=actor_id,
            actor_name=actor_name,
            started_at=now,
            lease_until=lease_until,
        )
        return replace(self, version=self.version + 1, results=(*results, attempt))

    def may_hold_unrecorded_items(self) -> bool:
        """Whether the tracker may hold items this record does not map yet.

        An attempt that was interrupted may have created an item it never recorded, and so
        may one whose item failed: a create whose answer was lost on the way back can still
        have succeeded. Only attempts since the last complete publication count.
        """
        for attempt in reversed(self.results[:-1]):
            if attempt.outcome is PublicationOutcome.PUBLISHED:
                return False
            if attempt.interrupted or any(
                item.result is ItemResult.FAILED for item in attempt.items
            ):
                return True
        return False

    def record(
        self, outcome: ItemOutcome, mapping: ExternalWorkItemMapping | None = None
    ) -> BacklogPublication:
        latest = self.latest
        if latest is None or not latest.running:
            raise InvalidPublicationError("Items are recorded only on a running attempt.")
        mappings = self.mappings
        if mapping is not None:
            if mapping.local_key != outcome.local_key:
                raise InvalidPublicationError("A mapping is recorded with its own item.")
            mappings = (
                *(item for item in mappings if item.local_key != mapping.local_key),
                mapping,
            )
        attempt = replace(latest, items=(*latest.items, outcome))
        return replace(
            self,
            version=self.version + 1,
            mappings=mappings,
            results=(*self.results[:-1], attempt),
        )

    def finish(self, now: datetime) -> BacklogPublication:
        latest = self.latest
        if latest is None or not latest.running:
            raise InvalidPublicationError("Only a running attempt can finish.")
        require_aware(now, "attempt finish")
        return replace(
            self,
            version=self.version + 1,
            results=(*self.results[:-1], replace(latest, finished_at=now)),
        )
