"""Atomic transaction coordinator for the in-memory adapter graph."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Protocol

from smb_requirement_agent.application.ports.external_work import check_external_result
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class _RevisionWriter(Protocol):
    """The part of governance's breakdown repository a checkpoint needs."""

    def create_current_revisions(self, requirement_id: RequirementId) -> None: ...


class MemoryTransactionParticipant(Protocol):
    def snapshot_state(self) -> object: ...

    def restore_state(self, state: object) -> None: ...


class InMemoryTransactionManager:
    """Coordinate all mutable memory stores with one reentrant lock.

    Participants remain simple repository adapters. Their collection-valued
    state is snapshotted only at the outer transaction boundary, and nested
    failures mark the entire logical mutation for rollback even when caught by
    an inner collaborator.
    """

    def __init__(
        self, source_changed: Callable[[RequirementId], None], lock: threading.RLock
    ) -> None:
        self._source_changed = source_changed
        self._lock = lock
        self._participants: list[MemoryTransactionParticipant] = []
        self._local = threading.local()
        self._projections: list[Callable[[RequirementId], None]] = []

    def project_on_commit(self, refresh: Callable[[RequirementId], None]) -> None:
        self._projections.append(refresh)

    def enroll(self, *participants: MemoryTransactionParticipant) -> None:
        with self._lock:
            for participant in participants:
                if participant not in self._participants:
                    self._participants.append(participant)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._lock:
            depth = int(getattr(self._local, "depth", 0))
            outer = depth == 0
            if outer:
                self._local.snapshot = self._snapshot()
                self._local.rollback_only = False
                self._local.revision_checkpoints = {}
            self._local.depth = depth + 1
            try:
                yield
            except BaseException:
                self._local.rollback_only = True
                raise
            finally:
                self._local.depth -= 1
                if outer:
                    try:
                        if bool(self._local.rollback_only):
                            self._restore(self._local.snapshot)
                        else:
                            try:
                                for (
                                    requirement_id,
                                    revisions,
                                ) in self._local.revision_checkpoints.values():
                                    revisions.create_current_revisions(requirement_id)
                                    for refresh in self._projections:
                                        refresh(requirement_id)
                            except BaseException:
                                self._restore(self._local.snapshot)
                                raise
                    finally:
                        del self._local.snapshot
                        del self._local.rollback_only
                        del self._local.revision_checkpoints
                        del self._local.depth

    def in_unit_of_work(self) -> bool:
        # external_call() sets the depth to 0 while the provider runs.
        return int(getattr(self._local, "depth", 0)) > 0

    def mark_rollback_only(self) -> None:
        if int(getattr(self._local, "depth", 0)) == 0:
            raise RuntimeError("No in-memory transaction is active.")
        self._local.rollback_only = True

    def lock_requirement(self, requirement_id: RequirementId) -> None:
        del requirement_id
        if int(getattr(self._local, "depth", 0)) == 0:
            raise RuntimeError("Requirement locks require an active in-memory transaction.")

    def try_lock_requirement(self, requirement_id: RequirementId) -> bool:
        self.lock_requirement(requirement_id)
        return True  # The active transaction already owns the shared graph lock.

    def checkpoint(
        self,
        requirement_id: RequirementId,
        revisions: _RevisionWriter,
    ) -> None:
        """Capture only the final workspace state for one logical mutation."""
        self._source_changed(requirement_id)
        if int(getattr(self._local, "depth", 0)) == 0:
            revisions.create_current_revisions(requirement_id)
            for refresh in self._projections:
                refresh(requirement_id)
            return
        self._local.revision_checkpoints[requirement_id.value] = (requirement_id, revisions)

    @contextmanager
    def external_call(self) -> Iterator[None]:
        """Release the graph lock while external work runs, then refresh rollback state."""
        depth = int(getattr(self._local, "depth", 0))
        if depth == 0:
            yield
            return
        if bool(getattr(self._local, "rollback_only", False)):
            raise RuntimeError("External calls require a clean outer in-memory transaction.")
        if self._snapshot() != self._local.snapshot or self._local.revision_checkpoints:
            raise RuntimeError("External providers cannot run after a transaction has written.")
        self._local.depth = 0
        for _ in range(depth):
            self._lock.release()
        try:
            yield
        finally:
            for _ in range(depth):
                self._lock.acquire()
            self._local.depth = depth
            self._local.snapshot = self._snapshot()
            self._local.rollback_only = False
            self._local.revision_checkpoints = {}

        check_external_result()

    def _snapshot(self) -> list[tuple[MemoryTransactionParticipant, object]]:
        return [(participant, participant.snapshot_state()) for participant in self._participants]

    @staticmethod
    def _restore(snapshots: list[tuple[MemoryTransactionParticipant, object]]) -> None:
        for participant, state in snapshots:
            participant.restore_state(state)
