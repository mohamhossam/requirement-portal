"""Connection contract shared by repositories and commit-time projections."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Protocol

from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.infrastructure.persistence.postgres_values import DbConnection


class PostgresSession(Protocol):
    def connection(self) -> AbstractContextManager[DbConnection]: ...
    def transaction(self) -> AbstractContextManager[None]: ...
    def mark_requirement_dirty(self, requirement_id: RequirementId) -> None: ...


class PostgresCommitSession:
    """Borrow an active commit connection without owning its transaction."""

    def __init__(self, connection: DbConnection) -> None:
        self._active = connection

    @contextmanager
    def connection(self) -> Iterator[DbConnection]:
        yield self._active

    @contextmanager
    def transaction(self) -> Iterator[None]:
        yield

    def mark_requirement_dirty(self, requirement_id: RequirementId) -> None:
        raise RuntimeError("A derived projection cannot mutate authoritative Requirement state.")
