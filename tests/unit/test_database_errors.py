"""A statement or lock timeout is a busy database: 503 `database_busy`, retried by jobs."""

from __future__ import annotations

import psycopg
import pytest
from psycopg import errors

from smb_requirement_agent.application.errors import DatabaseBusyError, PersistenceError
from smb_requirement_agent.infrastructure.persistence.database_errors import database_error
from smb_requirement_agent.workflows.application.public_errors import (
    FailureCategory,
    describe_public_error,
)
from smb_requirement_agent.workflows.application.use_cases.ai_job_execution import (
    TRANSIENT_FAILURE_CODES,
)


@pytest.mark.parametrize("cause", [errors.QueryCanceled(), errors.LockNotAvailable()])
def test_a_statement_or_lock_timeout_is_a_busy_database(cause: psycopg.Error) -> None:
    translated = database_error(cause, "Counting failed.")

    assert isinstance(translated, DatabaseBusyError)
    described = describe_public_error(translated)
    assert (described.code, described.category, described.retryable) == (
        "database_busy",
        FailureCategory.UNAVAILABLE,
        True,
    )
    assert described.code in TRANSIENT_FAILURE_CODES


@pytest.mark.parametrize(
    "cause",
    [
        errors.UniqueViolation(),
        errors.IdleInTransactionSessionTimeout(),
        psycopg.OperationalError(),
    ],
)
def test_other_database_failures_stay_internal(cause: psycopg.Error) -> None:
    translated = database_error(cause, "Saving failed.")

    assert type(translated) is PersistenceError
    assert describe_public_error(translated).code == "persistence"
