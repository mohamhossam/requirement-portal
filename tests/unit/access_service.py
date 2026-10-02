"""A real access service over a test's own repositories.

Use cases authorize through `RequirementAccessService`; tests that build use
cases by hand get one from the same requirement and access repositories they
already set up, so authorization is exercised, never stubbed.
"""

from __future__ import annotations

from smb_requirement_agent.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.application.ports.requirement_repository import RequirementRepositoryPort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.identity_access import RequirementAccessService
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.persistence import (
    in_memory_requirement_draft_repository as drafts,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_analysis_audit_repository import (
    InMemoryAnalysisAuditRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_identity import (
    InMemoryActorDirectory,
)
from smb_requirement_agent.infrastructure.time.fixed_clock import FixedClock
from tests.conftest import TEST_NOW
from tests.unit.transaction_stub import NoOpTransactionManager


def access_service_for(
    requirements: RequirementRepositoryPort,
    access: AccessRepositoryPort,
    transactions: TransactionManagerPort | None = None,
) -> RequirementAccessService:
    return RequirementAccessService(
        requirements,
        drafts.InMemoryRequirementDraftRepository(),
        access,
        InMemoryActorDirectory(FAKE_ACTORS),
        FixedClock(TEST_NOW),
        transactions or NoOpTransactionManager(),
        InMemoryAnalysisAuditRepository(lambda _: None),
    )
