"""Minimal transaction stub for isolated pure use-case tests only."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager

from smb_requirement_agent.application.ports.external_work import check_external_result
from smb_requirement_agent.domain.shared.identifiers import RequirementId


class NoOpTransactionManager:
    """Transaction boundary for immutable in-memory development adapters."""

    def transaction(self) -> AbstractContextManager[None]:
        return _nothing()

    def mark_rollback_only(self) -> None:
        """Memory use cases validate before mutation; no transaction to roll back."""

    def lock_requirement(self, requirement_id: RequirementId) -> None:
        del requirement_id

    def try_lock_requirement(self, requirement_id: RequirementId) -> bool:
        return True

    def external_call(self) -> AbstractContextManager[None]:
        return _external()


@contextmanager
def _nothing() -> Iterator[None]:
    yield


@contextmanager
def _external() -> Iterator[None]:
    yield
    check_external_result()
