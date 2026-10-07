"""Shared test fixtures.

Every API test gets its own container, so no state leaks between tests and no
test depends on a process-wide singleton.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Never

import pytest
from fastapi.testclient import TestClient
from smb_kernel.documents.text_extractor import SafeDocumentTextExtractor
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_knowledge import (
    KnowledgeReview,
    KnowledgeScreenEnsureOutcome,
    KnowledgeScreenEnsureResult,
)
from smb_requirement_agent.application.use_cases.documents import AssembleAnalysisDocuments
from smb_requirement_agent.application.use_cases.invalidate_approval_workflow import (
    InvalidateApprovalWorkflow,
)
from smb_requirement_agent.application.use_cases.invalidate_derived_artifacts import (
    InvalidateDerivedArtifacts,
)
from smb_requirement_agent.domain.knowledge.entities import KnowledgeScreen, KnowledgeScreenId
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence.in_memory_analysis_audit_repository import (
    InMemoryAnalysisAuditRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_analysis_repository import (
    InMemoryRequirementAnalysisRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_breakdown_review_repository import (
    InMemoryBreakdownReviewRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_document_repository import (
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_epic_repository import (
    InMemoryEpicRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_feature_repository import (
    InMemoryFeatureRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_story_repository import (
    InMemoryStoryRepository,
)
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

# The application resolves settings during startup, which TestClient triggers.
# Default the suite to the fake provider so no test needs provider credentials.
os.environ.setdefault("LLM_PROVIDER", LLMProvider.FAKE.value)
os.environ.setdefault("PERSISTENCE_PROVIDER", "memory")

FAKE_PROVIDER_SETTINGS = Settings(llm_provider=LLMProvider.FAKE)


@pytest.fixture
def container() -> Container:
    """A fresh object graph backed by the deterministic fake analyzer."""
    return build_container(FAKE_PROVIDER_SETTINGS)


@pytest.fixture
def client(container: Container) -> Generator[TestClient, None, None]:
    """A TestClient wired to an isolated container."""
    application = create_app(lambda: container)
    with TestClient(application) as c:
        yield c


TEST_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class NoOpKnowledgeScheduler:
    """Explicit old-slice test double for knowledge scheduling."""

    def schedule(self, requirement_id: object) -> None:
        del requirement_id

    def ensure(self, requirement_id: object) -> KnowledgeScreenEnsureResult:
        del requirement_id
        return KnowledgeScreenEnsureResult(KnowledgeScreenEnsureOutcome.CURRENT)


class NoOpAnswerSuggestionScheduler:
    """Explicit old-slice test double for automatic answer suggestions."""

    def schedule(self, requirement_id: object, questions: object) -> None:
        del requirement_id, questions


class AcceptAllSuggestionValidator:
    """Explicit old-slice test double for suggestion provenance validation."""

    def require_suggestion(
        self, requirement_id: object, question_id: object, suggestion_id: str
    ) -> Never:
        raise AssertionError("This fixture does not supply suggestions.")


class AlwaysReadyKnowledgeReview:
    """Explicit old-slice test double for the newly introduced confirmation gate."""

    def execute(self, requirement_id: RequirementId) -> KnowledgeReview:
        screen = KnowledgeScreen(
            KnowledgeScreenId(f"screen-{requirement_id.value}"),
            requirement_id,
            "test-ready",
            1,
            (),
            Provenance(TEST_NOW, "test", "test"),
        )
        return KnowledgeReview(screen, (), "test-ready")

    def require_ready(self, requirement_id: RequirementId) -> None:
        del requirement_id


def make_analysis_documents(
    repository: InMemoryDocumentRepository | None = None,
    max_characters: int = 60_000,
) -> AssembleAnalysisDocuments:
    """Build the required document-context collaborator for unit tests."""
    return AssembleAnalysisDocuments(
        repository or InMemoryDocumentRepository(),
        InMemoryDocumentStorage(),
        SafeDocumentTextExtractor(),
        max_characters,
    )


def make_invalidation(
    analysis_repository: RequirementAnalysisRepositoryPort | None = None,
    epic_repository: InMemoryEpicRepository | None = None,
    feature_repository: InMemoryFeatureRepository | None = None,
    story_repository: InMemoryStoryRepository | None = None,
    clock: FixedClock | None = None,
    audits: InMemoryAnalysisAuditRepository | None = None,
) -> InvalidateDerivedArtifacts:
    """Build the collaborator UpdateRequirement requires, with fresh defaults."""
    return InvalidateDerivedArtifacts(
        analysis_repository or InMemoryRequirementAnalysisRepository(),
        epic_repository or InMemoryEpicRepository(),
        feature_repository or InMemoryFeatureRepository(),
        story_repository or InMemoryStoryRepository(),
        clock or FixedClock(TEST_NOW),
        audits or InMemoryAnalysisAuditRepository(lambda requirement_id: None),
        InvalidateApprovalWorkflow(InMemoryBreakdownReviewRepository()),
    )
