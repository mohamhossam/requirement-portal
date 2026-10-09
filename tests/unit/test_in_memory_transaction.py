"""Atomic behavior of the shared in-memory unit of work."""

from __future__ import annotations

from threading import RLock
from typing import cast

import pytest

from smb_requirement_agent.governance.application.ports.breakdown_repository import (
    BreakdownRepositoryPort,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_transaction import (
    InMemoryTransactionManager,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class MutableParticipant:
    def __init__(self) -> None:
        self.values: dict[str, str] = {"state": "before"}

    def snapshot_state(self) -> object:
        return dict(self.values)

    def restore_state(self, state: object) -> None:
        self.values = dict(cast(dict[str, str], state))


class RevisionRecorder:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[str] = []
        self.fail = fail

    def snapshot_state(self) -> object:
        return list(self.calls)

    def restore_state(self, state: object) -> None:
        self.calls = list(cast(list[str], state))

    def create_current_revisions(self, requirement_id: RequirementId) -> None:
        self.calls.append(requirement_id.value)
        if self.fail:
            raise RuntimeError("revision persistence failed")


def test_nested_failure_marks_the_whole_memory_transaction_for_rollback() -> None:
    manager = InMemoryTransactionManager(lambda requirement_id: None, RLock())
    participant = MutableParticipant()
    manager.enroll(participant)

    with manager.transaction():
        participant.values["state"] = "outer"
        try:
            with manager.transaction():
                participant.values["state"] = "inner"
                raise RuntimeError("inner mutation failed")
        except RuntimeError:
            pass
        participant.values["late"] = "must also roll back"

    assert participant.values == {"state": "before"}


def test_memory_transaction_writes_one_final_revision_per_requirement() -> None:
    manager = InMemoryTransactionManager(lambda requirement_id: None, RLock())
    revisions = RevisionRecorder()
    requirement_id = RequirementId("requirement-1")

    with manager.transaction():
        manager.checkpoint(requirement_id, cast(BreakdownRepositoryPort, revisions))
        manager.checkpoint(requirement_id, cast(BreakdownRepositoryPort, revisions))

    assert revisions.calls == [requirement_id.value]


def test_revision_flush_failure_restores_all_enrolled_memory_state() -> None:
    manager = InMemoryTransactionManager(lambda requirement_id: None, RLock())
    participant = MutableParticipant()
    revisions = RevisionRecorder(fail=True)
    manager.enroll(participant, revisions)

    with pytest.raises(RuntimeError, match="revision persistence failed"):
        with manager.transaction():
            participant.values["state"] = "after"
            manager.checkpoint(
                RequirementId("requirement-1"),
                cast(BreakdownRepositoryPort, revisions),
            )

    assert participant.values == {"state": "before"}
    assert revisions.calls == []


def test_nested_external_work_commits_progress_independently() -> None:
    manager = InMemoryTransactionManager(lambda requirement_id: None, RLock())
    participant = MutableParticipant()
    manager.enroll(participant)
    with pytest.raises(RuntimeError, match="reject generation"):
        with manager.transaction(), manager.transaction():
            with manager.external_call():
                with manager.transaction():
                    participant.values["progress"] = "visible"
            participant.values["artifact"] = "discard"
            raise RuntimeError("reject generation")
    assert participant.values == {"state": "before", "progress": "visible"}
