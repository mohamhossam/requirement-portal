"""One translation from a PostgreSQL driver error to this application's persistence errors.

A statement cancelled by `statement_timeout` (SQLSTATE 57014) or a lock wait cut short by
`lock_timeout` (55P03) means the database is busy, not broken: callers see
`DatabaseBusyError`, which the API answers with 503 `database_busy` and jobs retry.
"""

from __future__ import annotations

import psycopg

from smb_requirement_agent.application.errors import DatabaseBusyError, PersistenceError

_BUSY_SQLSTATES = frozenset({"57014", "55P03"})


def database_error(exc: psycopg.Error, message: str) -> PersistenceError:
    """The persistence error to raise, from `exc`, for a failed database operation."""
    if exc.sqlstate in _BUSY_SQLSTATES:
        return DatabaseBusyError(message)
    return PersistenceError(message)
