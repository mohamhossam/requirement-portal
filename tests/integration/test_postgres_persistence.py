"""Live PostgreSQL migration, durability, and immutable revision checks."""

from __future__ import annotations

import hashlib
import os
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Never

import psycopg
import pytest
from psycopg import sql
from smb_kernel.documents.text_extractor import SafeDocumentTextExtractor
from smb_kernel.persistence.connector import (
    DirectPostgresConnector,
)
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.errors import DocumentStorageError
from smb_requirement_agent.application.exports import ExportFormat
from smb_requirement_agent.application.ports.ai_jobs import AiJobCommand, AiJobRecord
from smb_requirement_agent.application.ports.requirement_analyzer import (
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.application.ports.requirement_evidence_analyzer import (
    EvidenceFragmentCacheEntry,
)
from smb_requirement_agent.application.ports.requirement_knowledge import (
    KnowledgeScreenEnsureOutcome,
    KnowledgeScreenEnsureResult,
)
from smb_requirement_agent.application.ports.requirement_worklist import (
    WorkflowStatus,
    WorklistSort,
)
from smb_requirement_agent.application.ports.saved_views import (
    SavedRequirementView,
    SavedViewCriteria,
)
from smb_requirement_agent.application.use_cases.analysis_collaboration import (
    AnalysisCollaboration,
)
from smb_requirement_agent.application.use_cases.documents import AssembleAnalysisDocuments
from smb_requirement_agent.application.use_cases.export_breakdown import ExportBreakdown
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.domain.analysis.entities import (
    AnalysisDocumentReference,
    AnalysisQuestionChange,
    AnalysisRound,
    ClarificationQuestion,
    RequirementAnalysis,
)
from smb_requirement_agent.domain.analysis.errors import (
    ClarificationVersionConflictError,
    InvalidClarificationTransitionError,
)
from smb_requirement_agent.domain.analysis.value_objects import (
    AnalysisId,
    ClarificationKind,
    ClarificationSeverity,
    ClarificationSource,
    IntentProposal,
    IntentProposalId,
    IntentProposalKind,
    IntentProposalStatus,
    KnownFact,
    QuestionChangeAction,
    QuestionId,
)
from smb_requirement_agent.domain.architecture.entities import (
    ArchitectureDependency,
    ArchitectureImpact,
    SystemCapability,
    SystemReference,
)
from smb_requirement_agent.domain.document.entities import (
    SourceDocument,
    SourceDocumentVersion,
)
from smb_requirement_agent.domain.document.value_objects import (
    DocumentId,
    DocumentVersionId,
    ExtractionStatus,
)
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.epic.value_objects import (
    BusinessCase,
    BusinessOutcome,
    EpicId,
    EpicName,
    EpicStatus,
)
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.value_objects import (
    DeliveryDrop,
    FeatureId,
    FeatureName,
    FeatureOutcome,
    FeatureStatus,
    SplittingPattern,
    SplittingRationale,
)
from smb_requirement_agent.domain.identity.entities import (
    DraftOwnership,
    RequirementAccess,
)
from smb_requirement_agent.domain.identity.errors import RequirementAccessConflictError
from smb_requirement_agent.domain.jobs.entities import (
    AiJob,
    AiJobId,
    AiJobOperation,
    AiJobOrigin,
    AiJobStatus,
)
from smb_requirement_agent.domain.knowledge.entities import (
    AnswerSuggestion,
    AnswerSuggestionId,
    AnswerSuggestionSet,
    AnswerSuggestionSetId,
    AnswerSuggestionSource,
    KnowledgeChunk,
    KnowledgeChunkId,
    KnowledgeFinding,
    KnowledgeFindingId,
    KnowledgeRelationshipKind,
    KnowledgeScreen,
    KnowledgeScreenId,
    KnowledgeSourceKind,
    RelationshipEvidence,
)
from smb_requirement_agent.domain.requirement.entities import Requirement, RequirementDraft
from smb_requirement_agent.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
    RequirementVersion,
)
from smb_requirement_agent.domain.review.entities import (
    BreakdownReview,
    BreakdownStatus,
    Decision,
    DecisionId,
    Flag,
    FlagCategory,
    FlagId,
    FlagSeverity,
    ResolutionPolicy,
    ReviewSource,
    ReviewSourceKind,
)
from smb_requirement_agent.domain.story.entities import (
    StoryChangeOperation,
    StoryChangeProposal,
    StoryDraft,
    UserStory,
)
from smb_requirement_agent.domain.story.value_objects import (
    AcceptanceCriterion,
    BusinessValue,
    DesiredAction,
    StoryId,
    StoryProposalId,
    UserRole,
)
from smb_requirement_agent.infrastructure.exports.json_exporter import JsonBacklogExporter
from smb_requirement_agent.infrastructure.exports.xlsx_exporter import XlsxBacklogExporter
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.llm.fake_requirement_analyzer import (
    FakeRequirementAnalyzer,
)
from smb_requirement_agent.infrastructure.persistence.backfill_document_blobs import backfill
from smb_requirement_agent.infrastructure.persistence.in_memory_document_repository import (
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
)
from smb_requirement_agent.infrastructure.persistence.migration_runner import (
    MIGRATIONS,
    latest_packaged_migration,
    run_migrations,
)
from smb_requirement_agent.infrastructure.persistence.postgres_activity_reader import (
    PostgresActivityReadAdapter,
)
from smb_requirement_agent.infrastructure.persistence.postgres_ai_jobs import PostgresAiJobStore
from smb_requirement_agent.infrastructure.persistence.postgres_document_repository import (
    PostgresDocumentStorage,
)
from smb_requirement_agent.infrastructure.persistence.postgres_evidence_fragment_cache import (
    PostgresEvidenceFragmentCache,
)
from smb_requirement_agent.infrastructure.persistence.postgres_repositories import (
    PostgresActorDirectory,
    PostgresAnalysisAuditRepository,
    PostgresAnalysisRepository,
    PostgresEpicRepository,
    PostgresFeatureRepository,
    PostgresStoryChangeProposalRepository,
    PostgresStoryRepository,
)
from smb_requirement_agent.infrastructure.persistence.postgres_requirement_knowledge import (
    PostgresRequirementKnowledgeStore,
)
from smb_requirement_agent.infrastructure.persistence.postgres_saved_views import (
    PostgresSavedViewRepository,
)
from smb_requirement_agent.infrastructure.persistence.postgres_store import (
    REQUIRED_MAINTENANCE_MARKER,
)
from smb_requirement_agent.infrastructure.persistence.postgres_store import (
    PostgresStore as UnitOfWorkStore,
)
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
    ActorSnapshot,
)
from smb_requirement_agent.shared_kernel.approval import (
    Approval,
    ApprovalDecision,
    ApprovalId,
    ApprovalTarget,
    ApprovalTargetKind,
)
from smb_requirement_agent.shared_kernel.generation import GenerationStatus, Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.integration.postgres_fixture_store import (
    FixturePostgresStore as _PostgresStore,
)
from tests.reference_helpers import EmptyReferences
from tests.unit.access_service import access_service_for

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")


@pytest.fixture(autouse=True)
def isolated_postgres_database() -> Iterator[None]:
    """Keep integration examples independent while retaining the migration ledger."""
    if DATABASE_URL is None:
        yield
        return
    run_migrations(DATABASE_URL)
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        table_names = [
            str(row[0])
            for row in connection.execute(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'schema_migrations'"
            ).fetchall()
        ]
        if table_names:
            connection.execute(
                sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                    sql.SQL(", ").join(sql.Identifier(name) for name in table_names)
                )
            )
    yield


class _NoopWorklistProjection:
    def refresh(self, requirement_id: RequirementId) -> None:
        return None


def PostgresStore(database_url: str) -> _PostgresStore:
    """Construct the focused persistence adapter used by these repository tests."""
    return _PostgresStore(database_url, _NoopWorklistProjection())


def test_requirement_knowledge_and_suggestions_survive_postgres_restart() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    now = datetime.now(UTC)
    subject_id = RequirementId(str(uuid.uuid4()))
    related_id = RequirementId(str(uuid.uuid4()))
    unique_evidence = f"Customers order XGPON-{related_id.value} through BCRM."
    store = PostgresStore(DATABASE_URL)
    for requirement_id, title in ((subject_id, "Candidate"), (related_id, "Canonical")):
        store.add(
            Requirement(
                requirement_id,
                RequirementTitle(title),
                RequirementDescription(unique_evidence),
                RequirementStatus.DRAFT,
            )
        )
    knowledge = PostgresRequirementKnowledgeStore(store)
    chunk = KnowledgeChunk(
        KnowledgeChunkId(str(uuid.uuid4())),
        related_id,
        1,
        KnowledgeSourceKind.SOURCE,
        "business_need",
        unique_evidence,
        "chunk-fingerprint",
        f"/requirements/{related_id.value}/capture",
    )
    vector = (1.0, *((0.0,) * 767))
    knowledge.replace(related_id, "corpus-fingerprint", (chunk,), (vector,))
    evidence = RelationshipEvidence(
        chunk.id,
        related_id,
        chunk.field,
        chunk.text,
        chunk.evidence_path,
        chunk.fingerprint,
    )
    screen = KnowledgeScreen(
        KnowledgeScreenId(str(uuid.uuid4())),
        subject_id,
        "screen-fingerprint",
        1,
        (),
        Provenance(now, "integration-classifier", "knowledge-v1"),
    )
    finding = KnowledgeFinding(
        KnowledgeFindingId(str(uuid.uuid4())),
        screen.id,
        subject_id,
        1,
        related_id,
        1,
        KnowledgeRelationshipKind.POSSIBLE_DUPLICATE,
        "The outcomes overlap.",
        (evidence,),
    )
    screen = replace(screen, finding_ids=(finding.id,))
    knowledge.append_screen(screen, (finding,))
    suggestions = AnswerSuggestionSet(
        AnswerSuggestionSetId(str(uuid.uuid4())),
        subject_id,
        QuestionId(str(uuid.uuid4())),
        "question-fingerprint",
        (
            AnswerSuggestion(
                AnswerSuggestionId(str(uuid.uuid4())),
                "Use BCRM.",
                "Confirmed by related evidence.",
                (evidence,),
            ),
        ),
        Provenance(now, "integration-suggester", "suggestions-v1"),
    )
    knowledge.append_suggestion_set(suggestions)

    restarted = PostgresRequirementKnowledgeStore(PostgresStore(DATABASE_URL))
    loaded_screen = restarted.current_screen(subject_id)
    loaded_suggestions = restarted.latest_suggestion_set(subject_id, suggestions.question_id.value)

    assert loaded_screen == screen
    assert restarted.get_finding(finding.id) == finding
    assert loaded_suggestions == suggestions
    assert loaded_suggestions is not None
    assert (
        loaded_suggestions.suggestions[0].source_for(subject_id)
        is AnswerSuggestionSource.TRUSTED_KNOWLEDGE
    )
    assert restarted.search(unique_evidence, vector, subject_id, 20)[0].chunk == chunk


def test_analysis_and_automatic_suggestion_scheduling_roll_back_together() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    requirement_id = RequirementId(str(uuid.uuid4()))
    store = PostgresStore(DATABASE_URL)
    store.add(
        Requirement(
            requirement_id,
            RequirementTitle("Transactional suggestions"),
            RequirementDescription("Persist the analysis and its automatic jobs atomically."),
            RequirementStatus.DRAFT,
        )
    )

    class NoOpKnowledgeScheduler:
        def schedule(self, requirement_id: RequirementId) -> None:
            del requirement_id

        def ensure(self, requirement_id: RequirementId) -> KnowledgeScreenEnsureResult:
            del requirement_id
            return KnowledgeScreenEnsureResult(KnowledgeScreenEnsureOutcome.CURRENT)

    store.save_requirement(
        RequirementAccess(requirement_id).claim(FAKE_ACTORS[0], datetime(2026, 9, 7, tzinfo=UTC))
    )

    class FailingSuggestionScheduler:
        def schedule(
            self,
            requirement_id: RequirementId,
            questions: tuple[ClarificationQuestion, ...],
        ) -> None:
            del requirement_id, questions
            raise RuntimeError("suggestion queue unavailable")

    class NoOpSuggestionValidator:
        def require_suggestion(
            self,
            requirement_id: RequirementId,
            question_id: QuestionId,
            suggestion_id: str,
        ) -> Never:
            raise AssertionError("This fixture does not supply suggestions.")

    collaboration = AnalysisCollaboration(
        store,
        PostgresAnalysisRepository(store),
        PostgresAnalysisAuditRepository(store),
        FakeRequirementAnalyzer(),
        AssembleAnalysisDocuments(
            InMemoryDocumentRepository(),
            InMemoryDocumentStorage(),
            SafeDocumentTextExtractor(),
            60_000,
        ),
        store,
        PostgresActorDirectory(store),
        FixedClock(datetime(2026, 9, 7, tzinfo=UTC)),
        store,
        NoOpKnowledgeScheduler(),
        FailingSuggestionScheduler(),
        NoOpSuggestionValidator(),
        contexts=GenerationContextTokens(
            store,
            PostgresAnalysisRepository(store),
            PostgresAnalysisAuditRepository(store),
            InMemoryDocumentRepository(),
            PostgresEpicRepository(store),
            PostgresFeatureRepository(store),
            PostgresStoryRepository(store),
            PostgresStoryChangeProposalRepository(store),
            transactions=store,
            references=EmptyReferences(),
        ),
        references=EmptyReferences(),
        reference_grounding=EmptyReferences(),
        authorization=access_service_for(store, store, store),
    )

    with pytest.raises(RuntimeError, match="suggestion queue unavailable"):
        collaboration.generate(FAKE_ACTORS[0], requirement_id, force=False)

    restarted = PostgresStore(DATABASE_URL)
    assert PostgresAnalysisRepository(restarted).get_by_requirement_id(requirement_id) is None
    audit = PostgresAnalysisAuditRepository(restarted)
    assert audit.list_rounds(requirement_id) == []
    assert audit.list_questions(requirement_id) == []


def test_analysis_audit_rounds_and_questions_survive_restart_and_enforce_versions() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    requirement_id = RequirementId(str(uuid.uuid4()))
    analysis_id = AnalysisId(str(uuid.uuid4()))
    question_id = QuestionId(str(uuid.uuid4()))
    now = datetime.now(UTC)
    store = PostgresStore(DATABASE_URL)
    store.add(
        Requirement(
            requirement_id,
            RequirementTitle("Audited analysis"),
            RequirementDescription("Persist every collaborative answer."),
            RequirementStatus.DRAFT,
        )
    )
    analysis = RequirementAnalysis(
        requirement_id,
        (KnownFact("Audited fact"),),
        (),
        (),
        (),
        (),
        (),
        (),
        id=analysis_id,
        round_number=1,
        provenance=Provenance(now, "integration-model", "analysis-v4"),
        source_requirement_version=RequirementVersion(1),
        intent_proposals=(
            IntentProposal(
                IntentProposalId(str(uuid.uuid4())),
                IntentProposalKind.DESIRED_OUTCOME,
                "Customers can complete the audited journey.",
                "Observable outcome inferred from the need.",
                ("Journey completion can be observed.",),
            ).decide(
                IntentProposalStatus.EDITED,
                FAKE_ACTORS[0].snapshot(),
                now,
                1,
                replacement_statement="Customers complete the audited journey.",
            ),
        ),
    )
    question = ClarificationQuestion(
        question_id,
        requirement_id,
        analysis_id,
        ClarificationKind.OPEN_QUESTION,
        "Who owns the decision?",
        "Ownership is missing.",
        ClarificationSeverity.MEDIUM,
        True,
        ClarificationSource.AI,
    )
    audit = PostgresAnalysisAuditRepository(store)
    replacement_id = QuestionId(str(uuid.uuid4()))
    replacement = question.replacement(
        replacement_id,
        analysis_id,
        ClarificationKind.AMBIGUITY,
        "Which decision owner applies?",
        "The ownership gap needs more precise wording.",
    )
    round_ = AnalysisRound(
        analysis,
        (replacement_id,),
        (
            AnalysisQuestionChange(
                QuestionChangeAction.REPLACED,
                question_id,
                "The ownership gap needs more precise wording.",
                replacement_id,
            ),
        ),
    )
    audit.append_round(round_)
    audit.add_question(question.supersede())
    audit.add_question(replacement)

    restarted = PostgresAnalysisAuditRepository(PostgresStore(DATABASE_URL))
    assert restarted.list_rounds(requirement_id) == [round_]
    assert restarted.get_question(requirement_id, question_id) == question.supersede()
    assert restarted.get_question(requirement_id, replacement_id) == replacement

    drafted = replacement.save_draft("Partial answer", FAKE_ACTORS[0], now, 1)
    restarted.save_question(drafted)
    with pytest.raises(ClarificationVersionConflictError):
        restarted.save_question(drafted)
    resolved = drafted.resolve("Final answer", FAKE_ACTORS[0], now, 2)
    restarted.save_question(resolved)
    with pytest.raises(InvalidClarificationTransitionError):
        restarted.save_question(replace(resolved, version=4))

    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        with pytest.raises(psycopg.errors.RaiseException):
            connection.execute(
                "UPDATE analysis_rounds SET round_number = 2 WHERE analysis_id = %s",
                (analysis_id.value,),
            )


def test_migrations_are_idempotent_and_requirement_survives_adapter_restart() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    run_migrations(DATABASE_URL)
    requirement_id = RequirementId(str(uuid.uuid4()))
    original = Requirement(
        requirement_id,
        RequirementTitle("Durable requirement"),
        RequirementDescription("Preserve this human-authored source."),
        RequirementStatus.DRAFT,
    )

    PostgresStore(DATABASE_URL).add(original)
    restarted = PostgresStore(DATABASE_URL)

    assert restarted.get(requirement_id) == original
    assert len(restarted.list_requirement_revisions(requirement_id)) == 1

    updated = original.update(
        RequirementTitle("Durable requirement v2"),
        RequirementDescription("Preserve this updated human-authored source."),
    )
    restarted.save(updated)
    history = PostgresStore(DATABASE_URL).list_requirement_revisions(requirement_id)
    assert [item.requirement.title.value for item in history] == [
        "Durable requirement",
        "Durable requirement v2",
    ]


def test_readiness_requires_the_newest_migration_and_maintenance_marker() -> None:
    assert DATABASE_URL is not None
    store = UnitOfWorkStore(DirectPostgresConnector(DATABASE_URL), lambda *_: None, lambda *_: None)
    newest = latest_packaged_migration()
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(
            "INSERT INTO maintenance_markers (name) VALUES (%s) ON CONFLICT DO NOTHING",
            (REQUIRED_MAINTENANCE_MARKER,),
        )
        assert store.readiness() is True

        # A schema one migration behind must not be reported ready.
        connection.execute("DELETE FROM schema_migrations WHERE version=%s", (newest,))
        try:
            assert store.readiness() is False
        finally:
            connection.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (newest,))

        connection.execute(
            "DELETE FROM maintenance_markers WHERE name=%s", (REQUIRED_MAINTENANCE_MARKER,)
        )
        assert store.readiness() is False


def test_migration_012_cancels_only_queued_automatic_knowledge_jobs() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    requirement_id = RequirementId(str(uuid.uuid4()))
    now = datetime.now(UTC)
    store = PostgresStore(DATABASE_URL)
    store.add(
        Requirement(
            requirement_id,
            RequirementTitle("Knowledge migration selection"),
            RequirementDescription("Only obsolete automatic queued screens are cancelled."),
            RequirementStatus.DRAFT,
        )
    )
    jobs = PostgresAiJobStore(store)

    def add_job(
        name: str,
        operation: AiJobOperation,
        origin: AiJobOrigin,
        status: AiJobStatus,
    ) -> AiJob:
        queued = AiJob(
            AiJobId(f"{name}-{uuid.uuid4()}"),
            requirement_id,
            operation,
            AiJobStatus.QUEUED,
            ActorSnapshot(ActorId(f"migration-{name}"), name),
            now,
            now,
            f"migration-{name}-{uuid.uuid4()}",
            hashlib.sha256(f"migration-{name}-{uuid.uuid4()}".encode()).hexdigest(),
            origin=origin,
        )
        jobs.add(AiJobRecord(queued, AiJobCommand({})))
        if status is AiJobStatus.RUNNING:
            queued = queued.claim(now)
            jobs.save(queued)
        elif status is AiJobStatus.SUCCEEDED:
            queued = queued.claim(now)
            jobs.save(queued)
            queued = queued.succeed((), now)
            jobs.save(queued)
        return queued

    target = add_job(
        "target",
        AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE,
        AiJobOrigin.AUTOMATIC,
        AiJobStatus.QUEUED,
    )
    preserved = [
        add_job(
            "running",
            AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE,
            AiJobOrigin.AUTOMATIC,
            AiJobStatus.RUNNING,
        ),
        add_job(
            "user",
            AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE,
            AiJobOrigin.USER,
            AiJobStatus.QUEUED,
        ),
        add_job(
            "suggestion",
            AiJobOperation.SUGGEST_CLARIFICATION_ANSWERS,
            AiJobOrigin.AUTOMATIC,
            AiJobStatus.QUEUED,
        ),
        add_job(
            "completed",
            AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE,
            AiJobOrigin.AUTOMATIC,
            AiJobStatus.SUCCEEDED,
        ),
    ]

    migration = (MIGRATIONS / "012_cancel_queued_automatic_knowledge_screens.sql").read_text(
        encoding="utf-8"
    )
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(migration)
        connection.execute(migration)
        statuses = {
            str(row[0]): str(row[1])
            for row in connection.execute(
                "SELECT job_id, status FROM ai_jobs WHERE requirement_id=%s",
                (requirement_id.value,),
            ).fetchall()
        }
        assert statuses[target.id.value] == AiJobStatus.CANCELLED.value
        assert all(statuses[item.id.value] == item.status.value for item in preserved)
        connection.rollback()
    cleanup = PostgresAiJobStore(PostgresStore(DATABASE_URL))
    for item in (target, *preserved):
        current = cleanup.get(item.id)
        if current is None or current.job.status.terminal:
            continue
        terminal = (
            current.job.request_cancellation(now)
            if current.job.status is AiJobStatus.QUEUED
            else current.job.cancel(now)
        )
        cleanup.save(terminal)


def test_postgres_automatic_reservation_is_concurrent_and_attempt_idempotent() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    requirement_id = RequirementId(str(uuid.uuid4()))
    now = datetime.now(UTC)
    store = PostgresStore(DATABASE_URL)
    store.add(
        Requirement(
            requirement_id,
            RequirementTitle("Concurrent ensure"),
            RequirementDescription("Concurrent lazy entry creates one screening attempt."),
            RequirementStatus.DRAFT,
        )
    )
    fingerprint = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()

    def reserve(index: int) -> tuple[str, bool]:
        job = AiJob(
            AiJobId(str(uuid.uuid4())),
            requirement_id,
            AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE,
            AiJobStatus.QUEUED,
            ActorSnapshot(ActorId("automatic-system"), "Automatic system"),
            now,
            now,
            f"automatic-reservation-{index}-{uuid.uuid4()}",
            fingerprint,
            origin=AiJobOrigin.AUTOMATIC,
        )
        reserved, created = PostgresAiJobStore(PostgresStore(DATABASE_URL)).reserve_automatic(
            AiJobRecord(job, AiJobCommand({"knowledge_fingerprint": fingerprint}))
        )
        return reserved.job.id.value, created

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, range(2)))

    assert sum(created for _, created in results) == 1
    assert len({job_id for job_id, _ in results}) == 1
    persisted = PostgresAiJobStore(PostgresStore(DATABASE_URL)).get(AiJobId(results[0][0]))
    assert persisted is not None
    PostgresAiJobStore(PostgresStore(DATABASE_URL)).save(persisted.job.request_cancellation(now))


def test_postgres_automatic_reservation_rolls_back_with_its_business_action() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    requirement_id = RequirementId(str(uuid.uuid4()))
    now = datetime.now(UTC)
    store = PostgresStore(DATABASE_URL)
    store.add(
        Requirement(
            requirement_id,
            RequirementTitle("Transactional automatic reservation"),
            RequirementDescription("The job must roll back with a failed business action."),
            RequirementStatus.DRAFT,
        )
    )
    job = AiJob(
        AiJobId(str(uuid.uuid4())),
        requirement_id,
        AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE,
        AiJobStatus.QUEUED,
        ActorSnapshot(ActorId("automatic-system"), "Automatic system"),
        now,
        now,
        f"automatic-rollback-{uuid.uuid4()}",
        hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest(),
        origin=AiJobOrigin.AUTOMATIC,
    )
    jobs = PostgresAiJobStore(store)

    with store.transaction():
        _, created = jobs.reserve_automatic(
            AiJobRecord(job, AiJobCommand({"knowledge_fingerprint": "rollback"}))
        )
        assert created
        store.mark_rollback_only()

    assert PostgresAiJobStore(PostgresStore(DATABASE_URL)).get(job.id) is None


def test_database_rejects_revision_update_and_delete() -> None:
    assert DATABASE_URL is not None
    requirement_id = RequirementId(str(uuid.uuid4()))
    store = PostgresStore(DATABASE_URL)
    store.add(
        Requirement(
            requirement_id,
            RequirementTitle("Immutable history"),
            RequirementDescription("The revision row cannot be rewritten."),
            RequirementStatus.DRAFT,
        )
    )

    with psycopg.connect(DATABASE_URL) as connection, pytest.raises(psycopg.Error):
        connection.execute(
            "DELETE FROM requirement_revisions WHERE requirement_id = %s",
            (requirement_id.value,),
        )


def test_rollback_only_discards_current_state_and_revision_together() -> None:
    assert DATABASE_URL is not None
    requirement_id = RequirementId(str(uuid.uuid4()))
    store = PostgresStore(DATABASE_URL)

    with store.transaction():
        store.add(
            Requirement(
                requirement_id,
                RequirementTitle("Rollback requirement"),
                RequirementDescription("Neither current state nor history should commit."),
                RequirementStatus.DRAFT,
            )
        )
        store.mark_rollback_only()

    restarted = PostgresStore(DATABASE_URL)
    assert restarted.get(requirement_id) is None
    assert restarted.list_requirement_revisions(requirement_id) == []


def test_story_order_proposal_and_revision_survive_adapter_restart() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    suffix = str(uuid.uuid4())
    requirement_id = RequirementId(suffix)
    epic_id = EpicId(f"epic-{suffix}")
    feature_id = FeatureId(f"feature-{suffix}")
    generated_at = datetime(2026, 1, 1, tzinfo=UTC)
    provenance = Provenance(generated_at, "fake", "story-v1")
    requirement = Requirement(
        requirement_id,
        RequirementTitle("Durable Story tree"),
        RequirementDescription("Keep ordered Stories and pending previews after restart."),
        RequirementStatus.DRAFT,
    )
    analysis = RequirementAnalysis(
        requirement_id=requirement_id,
        known_facts=(KnownFact("The Feature is ready"),),
        constraints=(),
        business_rules=(),
        assumptions=(),
        open_questions=(),
        ambiguities=(),
        potential_dependencies=(),
        confirmed_at=generated_at,
    )
    epic = Epic(
        id=epic_id,
        requirement_id=requirement_id,
        name=EpicName("Durable Epic"),
        outcome=BusinessOutcome("The capability remains traceable"),
        business_case=BusinessCase("Review history is preserved"),
        status=EpicStatus.APPROVED,
        provenance=provenance,
    )
    feature = Feature(
        id=feature_id,
        epic_id=epic_id,
        name=FeatureName("Durable Feature"),
        outcome=FeatureOutcome("Stories remain ordered"),
        delivery_drop=DeliveryDrop.MVP,
        splitting_pattern=SplittingPattern.JOURNEY_STAGE,
        splitting_rationale=SplittingRationale("A separately reviewable journey stage"),
        status=FeatureStatus.APPROVED,
        provenance=provenance,
        architecture=ArchitectureImpact(
            "postgres-test-v1",
            generated_at,
            (
                SystemReference(
                    "bcrm",
                    "BCRM",
                    True,
                    (SystemCapability("assisted-sales", "Assisted sales"),),
                ),
                SystemReference("declared-cpp", "CPP", False),
            ),
            (ArchitectureDependency("bcrm", "declared-cpp", "Assisted hand-off"),),
        ),
    )

    def story(number: int) -> UserStory:
        return UserStory(
            id=StoryId(f"story-{number}-{suffix}"),
            feature_id=feature_id,
            role=UserRole("SMB customer"),
            action=DesiredAction(f"complete step {number}"),
            value=BusinessValue("I can finish the journey"),
            acceptance_criteria=(
                AcceptanceCriterion("I am eligible", f"I complete step {number}", "it succeeds"),
            ),
            status=GenerationStatus.GENERATED,
            provenance=provenance,
            architecture=feature.architecture,
        )

    stories = [story(1), story(2)]
    proposal = StoryChangeProposal(
        id=StoryProposalId(f"proposal-{suffix}"),
        feature_id=feature_id,
        operation=StoryChangeOperation.MERGE,
        source_story_ids=tuple(item.id for item in stories),
        source_fingerprint="unchanged-source-fingerprint",
        candidates=(
            StoryDraft(
                role=UserRole("SMB customer"),
                action=DesiredAction("complete both steps"),
                value=BusinessValue("I finish the journey"),
                acceptance_criteria=(
                    AcceptanceCriterion("I am eligible", "I complete both steps", "they succeed"),
                ),
                provenance=provenance,
            ),
        ),
    )
    flag_id = FlagId(f"flag-{suffix}")
    decision = Decision(
        DecisionId(f"decision-{suffix}"),
        "Accept the coordinated dependency",
        "The owning teams have agreed the hand-off.",
        generated_at,
        flag_id,
    )
    review = BreakdownReview(
        requirement_id=requirement_id,
        generated_at=generated_at,
        ruleset_version="postgres-review-v1",
        evidence_fingerprint="postgres-review-fingerprint",
        dependencies=(),
        risks=(),
        flags=(
            Flag(
                flag_id,
                FlagCategory.ARCHITECTURE,
                FlagSeverity.WARNING,
                "Cross-system hand-off",
                "The Feature crosses BCRM and CPP.",
                ReviewSource(ReviewSourceKind.FEATURE, feature_id.value, feature.name.value),
                ResolutionPolicy.DECISION,
            ),
        ),
        recommendations=(),
    ).resolve(flag_id, decision)

    store = PostgresStore(DATABASE_URL)
    with store.transaction():
        store.add(requirement)
        store.save_analysis(analysis)
        store.save_epic(epic)
        store.replace_features(epic_id, [feature], store.feature_set_version(epic_id))
        store.replace_stories(feature_id, stories, store.story_set_version(feature_id))
        store.save_story_proposal(proposal)
        store.save_breakdown_review(review)

    restarted = PostgresStore(DATABASE_URL)
    assert restarted.get_stories(feature_id) == stories
    assert restarted.list_story_proposals(feature_id) == [proposal]
    assert restarted.get_breakdown_review(requirement_id) == review
    revisions = restarted.list_breakdown_revisions(requirement_id)
    assert revisions[-1].stories == tuple(stories)
    assert revisions[-1].review == review
    snapshot = next(
        item for item in restarted.list_snapshots() if item.requirement.id == requirement_id
    )
    assert snapshot.requirement == requirement
    assert snapshot.analysis == analysis
    assert snapshot.epic == epic
    assert snapshot.features == (feature,)
    assert snapshot.stories == tuple(stories)
    assert snapshot.updated_at == revisions[-1].created_at


def test_document_metadata_and_immutable_versions_survive_adapter_restart() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    suffix = str(uuid.uuid4())
    requirement_id = RequirementId(suffix)
    content = b"Durable source text"
    version = SourceDocumentVersion(
        id=DocumentVersionId(f"version-{suffix}"),
        number=1,
        filename="source.txt",
        mime_type="text/plain",
        size_bytes=len(content),
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        extraction_status=ExtractionStatus.READY,
        created_at=datetime(2026, 9, 3, tzinfo=UTC),
        extracted_text=content.decode(),
    )
    document = SourceDocument(
        id=DocumentId(f"document-{suffix}"),
        requirement_id=requirement_id,
        versions=(version,),
    ).set_included(True)
    store = PostgresStore(DATABASE_URL)
    store.add(
        Requirement(
            requirement_id,
            RequirementTitle("Document durability"),
            RequirementDescription("Retain exact document metadata across restart."),
            RequirementStatus.DRAFT,
        )
    )
    store.add_document(document)

    restarted = PostgresStore(DATABASE_URL)

    assert restarted.get_document(document.id) == document
    assert restarted.list_documents(requirement_id=requirement_id) == [document]


def test_historical_document_reference_backfill_is_resumable_and_integrity_checked(
    tmp_path: Path,
) -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    suffix = str(uuid.uuid4())
    requirement_id = RequirementId(f"historical-document-{suffix}")
    version_id = f"historical-version-{suffix}"
    content = b"historical immutable source"
    checksum = hashlib.sha256(content).hexdigest()
    root = tmp_path / "legacy-blobs"
    root.mkdir()
    (root / f"{version_id}.blob").write_bytes(content)
    store = PostgresStore(DATABASE_URL)
    analysis = RequirementAnalysis(
        requirement_id,
        known_facts=(KnownFact("Historical evidence was used."),),
        constraints=(),
        business_rules=(),
        assumptions=(),
        open_questions=(),
        ambiguities=(),
        potential_dependencies=(),
        document_references=(
            AnalysisDocumentReference(
                f"historical-document-metadata-{suffix}",
                version_id,
                "historical.txt",
                checksum,
            ),
        ),
    )
    with store.transaction():
        store.add(
            Requirement(
                requirement_id,
                RequirementTitle("Historical document import"),
                RequirementDescription("Import bytes reachable only from immutable history."),
                RequirementStatus.DRAFT,
            )
        )
        store.save_analysis(analysis)
    store.delete_analysis(requirement_id)

    assert backfill(DATABASE_URL, str(root)) == 1
    assert backfill(DATABASE_URL, str(root)) == 0
    storage = PostgresDocumentStorage(PostgresStore(DATABASE_URL))
    assert storage.get(DocumentVersionId(version_id)) == content

    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            "UPDATE document_blobs SET content=%s WHERE document_version_id=%s",
            (b"x" * len(content), version_id),
        )
    with pytest.raises(DocumentStorageError, match="integrity"):
        storage.get(DocumentVersionId(version_id))


def test_identity_access_draft_ownership_and_revision_survive_restart() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    store = PostgresStore(DATABASE_URL)
    now = datetime(2026, 9, 3, tzinfo=UTC)
    requirement_id = RequirementId(str(uuid.uuid4()))
    draft_id = RequirementId(str(uuid.uuid4()))
    owner = ActorProfile(ActorId(f"actor-{uuid.uuid4()}"), "Durable Owner", "owner@example.test")
    reviewer_suffix = str(uuid.uuid4())
    reviewer = ActorProfile(
        ActorId(f"actor-{reviewer_suffix}"),
        f"Durable Reviewer {reviewer_suffix}",
        "reviewer@example.test",
    )
    requirement = Requirement(
        requirement_id,
        RequirementTitle("Identity durability"),
        RequirementDescription("Persist access independently of the identity provider."),
        RequirementStatus.DRAFT,
    )
    draft = RequirementDraft(
        draft_id,
        "Private draft",
        "",
        "",
        "",
        (),
        (),
        (),
        (),
        RequirementVersion(1),
        now,
    )
    access = (
        RequirementAccess(requirement_id).claim(owner, now).assign_reviewer(owner, reviewer, now)
    )
    ownership = DraftOwnership(draft_id).claim(owner, now)

    with store.transaction():
        store.add(requirement)
        store.record_actor(owner)
        store.record_actor(reviewer)
        store.save_requirement(access)
        store.add_draft(draft)
        store.save_draft_ownership(ownership)

    restarted = PostgresStore(DATABASE_URL)
    assert restarted.get_actor(owner.id) == owner
    assert restarted.search_actors(reviewer_suffix, 10) == [reviewer]
    assert restarted.get_requirement(requirement_id) == access
    assert restarted.get_draft_ownership(draft_id) == ownership
    history = restarted.list_requirement_revisions(requirement_id)
    assert len(history) == 1
    assert history[0].access == access

    restarted.record_actor(ActorProfile(owner.id, "Renamed Owner", owner.email))
    assert len(restarted.list_requirement_revisions(requirement_id)) == 1

    competing = RequirementAccess(requirement_id).claim(reviewer, now)
    with pytest.raises(RequirementAccessConflictError):
        restarted.save_requirement(competing)


def test_existing_postgres_requirement_remains_explicitly_unowned() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    store = PostgresStore(DATABASE_URL)
    requirement_id = RequirementId(str(uuid.uuid4()))
    store.add(
        Requirement(
            requirement_id,
            RequirementTitle("Pre-identity row"),
            RequirementDescription("Migration must not invent an owner."),
            RequirementStatus.DRAFT,
        )
    )

    assert store.get_requirement(requirement_id) is None
    assert store.list_requirement_revisions(requirement_id)[0].access is None


def test_ai_job_survives_adapter_restart_and_can_be_claimed() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    requirement_id = RequirementId(str(uuid.uuid4()))
    # The integration database may contain legitimate queued application jobs.
    # Give this fixture deterministic priority without deleting or claiming them.
    now = datetime(2000, 1, 1, tzinfo=UTC)
    store = PostgresStore(DATABASE_URL)
    store.add(
        Requirement(
            requirement_id,
            RequirementTitle("Durable AI job"),
            RequirementDescription("The queue survives API process restarts."),
            RequirementStatus.DRAFT,
        )
    )
    record = AiJobRecord(
        AiJob(
            AiJobId(str(uuid.uuid4())),
            requirement_id,
            AiJobOperation.RESOLVE_CLARIFICATION_QUESTIONS,
            AiJobStatus.QUEUED,
            ActorSnapshot(ActorId("integration-owner"), "Integration Owner"),
            now,
            now,
            str(uuid.uuid4()),
            hashlib.sha256(b"durable-job").hexdigest(),
        ),
        AiJobCommand(
            {
                "answers": [
                    {
                        "question_id": "question-1",
                        "answer": "Confirmed answer",
                        "expected_version": 1,
                    }
                ]
            }
        ),
    )
    automatic = replace(
        record.job,
        id=AiJobId(str(uuid.uuid4())),
        operation=AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE,
        created_at=now - timedelta(seconds=1),
        updated_at=now - timedelta(seconds=1),
        idempotency_key=str(uuid.uuid4()),
        command_fingerprint=hashlib.sha256(b"older-automatic-job").hexdigest(),
        origin=AiJobOrigin.AUTOMATIC,
    )
    job_store = PostgresAiJobStore(store)
    job_store.add(AiJobRecord(automatic, AiJobCommand({})))
    job_store.add(record)

    restarted = PostgresAiJobStore(PostgresStore(DATABASE_URL))
    assert restarted.get(record.job.id) == record
    claimed = restarted.claim_next("integration-worker", now, now + timedelta(seconds=30))
    assert claimed is not None
    assert claimed.job.status is AiJobStatus.RUNNING
    progressed = claimed.job.report_progress(
        "analyzing_evidence", 2, 5, "BUC 2", now + timedelta(seconds=1)
    )
    restarted.save(progressed)
    persisted = PostgresAiJobStore(PostgresStore(DATABASE_URL)).get(record.job.id)
    assert persisted is not None
    assert persisted.job.phase == "analyzing_evidence"
    assert persisted.job.completed_units == 2
    assert persisted.job.total_units == 5
    assert persisted.job.current_section_label == "BUC 2"
    restarted.save(persisted.job.succeed((), now + timedelta(seconds=2)))
    restarted.save(automatic.request_cancellation(now))


def test_deferred_ai_job_releases_requirement_lease_without_consuming_attempt() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    requirement_id = RequirementId(str(uuid.uuid4()))
    now = datetime(2000, 1, 1, tzinfo=UTC)
    store = PostgresStore(DATABASE_URL)
    store.add(
        Requirement(
            requirement_id,
            RequirementTitle("Index-gated screen"),
            RequirementDescription("A screen waits for the Requirement index."),
            RequirementStatus.DRAFT,
        )
    )
    job = AiJob(
        AiJobId(str(uuid.uuid4())),
        requirement_id,
        AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE,
        AiJobStatus.QUEUED,
        ActorSnapshot(ActorId("system:requirement-knowledge"), "Automatic"),
        now,
        now,
        str(uuid.uuid4()),
        hashlib.sha256(b"deferred-screen").hexdigest(),
        origin=AiJobOrigin.AUTOMATIC,
    )
    job_store = PostgresAiJobStore(store)
    job_store.add(AiJobRecord(job, AiJobCommand({})))
    claimed = job_store.claim_next("worker-a", now, now + timedelta(seconds=30))
    assert claimed is not None and claimed.attempt_token is not None
    assert claimed.job.attempt_count == 1

    assert not job_store.save_fenced(claimed.job.defer(now), "worker-a", "stale", now)
    assert job_store.save_fenced(claimed.job.defer(now), "worker-a", claimed.attempt_token, now)
    queued = PostgresAiJobStore(PostgresStore(DATABASE_URL)).get(job.id)
    assert queued is not None
    assert queued.job.status is AiJobStatus.QUEUED and queued.job.attempt_count == 0
    assert queued.worker_id is None and queued.attempt_token is None
    assert not job_store.heartbeat(
        job.id, "worker-a", claimed.attempt_token, now, now + timedelta(seconds=30)
    )

    # The Requirement lease was released immediately: another worker can claim.
    reclaimed = job_store.claim_next("worker-b", now, now + timedelta(seconds=30))
    assert reclaimed is not None and reclaimed.job.id == job.id
    assert reclaimed.job.attempt_count == 1
    assert reclaimed.attempt_token != claimed.attempt_token


def test_evidence_fragment_cache_survives_postgres_restart() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    key = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
    now = datetime.now(UTC)
    candidate = RequirementAnalysisCandidate(
        known_facts=["A packet-supported fact."],
        constraints=[],
        business_rules=[],
        assumptions=[],
        open_questions=[],
        ambiguities=[],
        potential_dependencies=[],
        intent_proposals=[],
        model="integration-model",
        prompt_version="analysis-v5-structured-evidence",
    )
    PostgresEvidenceFragmentCache(PostgresStore(DATABASE_URL)).put(
        key, EvidenceFragmentCacheEntry(candidate, now)
    )

    loaded = PostgresEvidenceFragmentCache(PostgresStore(DATABASE_URL)).get(key)

    assert loaded is not None
    assert loaded.candidate == candidate
    assert loaded.generated_at == now


def test_saved_requirement_view_survives_adapter_restart() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    now = datetime.now(UTC)
    view = SavedRequirementView(
        str(uuid.uuid4()),
        ActorId(f"saved-view-owner-{uuid.uuid4()}"),
        "My blocking questions",
        SavedViewCriteria(
            "fibre",
            (WorkflowStatus.NEEDS_ANSWERS,),
            WorklistSort.TITLE_ASC,
            ActorId("fake-owner"),
            True,
        ),
        1,
        now,
        now,
    )
    PostgresSavedViewRepository(PostgresStore(DATABASE_URL)).add(view)

    restarted = PostgresSavedViewRepository(PostgresStore(DATABASE_URL))

    assert restarted.get(view.id) == view
    assert restarted.list_for_actor(view.actor_id) == [view]


def test_postgres_activity_projection_reads_immutable_history_in_bulk() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    requirement_id = RequirementId(str(uuid.uuid4()))
    store = PostgresStore(DATABASE_URL)
    store.add(
        Requirement(
            requirement_id,
            RequirementTitle("Bulk activity projection"),
            RequirementDescription("Project this persisted Requirement revision."),
            RequirementStatus.DRAFT,
        )
    )
    projection = PostgresActivityReadAdapter(
        store,
        PostgresAiJobStore(store),
        PostgresRequirementKnowledgeStore(store),
        PostgresAnalysisAuditRepository(store),
    )

    events = [item for item in projection.list_events() if item.requirement_id == requirement_id]

    assert len(events) == 1
    assert events[0].action.value == "requirement_created"
    assert events[0].actor is None
    assert events[0].sources[0].source_id == f"{requirement_id.value}:1"
    assert projection.list_events_for_requirement(requirement_id) == events
    projected_again = next(
        item for item in projection.list_events() if item.requirement_id == requirement_id
    )
    assert events[0].id == projected_again.id


def test_approved_revision_exports_after_postgres_restart() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    suffix = str(uuid.uuid4())
    requirement_id = RequirementId(suffix)
    epic_id = EpicId(f"epic-{suffix}")
    feature_id = FeatureId(f"feature-{suffix}")
    now = datetime.now(UTC)
    provenance = Provenance(now, "integration-model", "export-v1")
    owner = ActorProfile(ActorId(f"owner-{suffix}"), "Integration Owner")
    requirement = Requirement(
        requirement_id,
        RequirementTitle("Restart-safe export"),
        RequirementDescription("Export the exact approved database revision."),
        RequirementStatus.DRAFT,
    )
    epic = Epic(
        id=epic_id,
        requirement_id=requirement_id,
        name=EpicName("Portable backlog"),
        outcome=BusinessOutcome("The approved tree is portable"),
        business_case=BusinessCase("Downstream tools can consume a stable contract"),
        status=EpicStatus.APPROVED,
        provenance=provenance,
    )
    feature = Feature(
        id=feature_id,
        epic_id=epic_id,
        name=FeatureName("Neutral export"),
        outcome=FeatureOutcome("A revision can be downloaded"),
        delivery_drop=DeliveryDrop.MVP,
        splitting_pattern=SplittingPattern.COMPONENT_SYSTEM,
        splitting_rationale=SplittingRationale("A separate integration boundary"),
        status=FeatureStatus.APPROVED,
        provenance=provenance,
    )
    story = UserStory(
        id=StoryId(f"story-{suffix}"),
        feature_id=feature_id,
        role=UserRole("Requirement Owner"),
        action=DesiredAction("download the approved revision"),
        value=BusinessValue("I can share the backlog"),
        acceptance_criteria=(
            AcceptanceCriterion("the backlog is approved", "I export it", "the hierarchy remains"),
        ),
        status=GenerationStatus.APPROVED,
        provenance=provenance,
    )
    fingerprint = f"approved-{suffix}"
    approval = Approval(
        ApprovalId(f"approval-{suffix}"),
        ApprovalTarget(ApprovalTargetKind.BREAKDOWN, requirement_id.value),
        ApprovalDecision.APPROVED,
        fingerprint,
        owner.snapshot(),
        now,
    )
    review = BreakdownReview(
        requirement_id=requirement_id,
        generated_at=now,
        ruleset_version="export-review-v1",
        evidence_fingerprint=f"evidence-{suffix}",
        dependencies=(),
        risks=(),
        flags=(),
        recommendations=(),
        status=BreakdownStatus.UNDER_REVIEW,
        submitted_fingerprint=fingerprint,
    ).approve_breakdown(approval)

    store = PostgresStore(DATABASE_URL)
    with store.transaction():
        store.add(requirement)
        store.save_requirement(RequirementAccess(requirement_id).claim(owner, now))
        store.save_epic(epic)
        store.replace_features(epic_id, [feature], store.feature_set_version(epic_id))
        store.replace_stories(feature_id, [story], store.story_set_version(feature_id))
        store.save_breakdown_review(review)

    restarted = PostgresStore(DATABASE_URL)
    revision = restarted.list_breakdown_revisions(requirement_id)[-1]
    use_case = ExportBreakdown(
        restarted,
        access_service_for(restarted, restarted, restarted),
        restarted,
        (JsonBacklogExporter(), XlsxBacklogExporter()),
    )

    artifact = use_case.execute(requirement_id, revision.number, ExportFormat.JSON, owner)

    assert artifact.content.startswith(b'{\n  "schema_version": "1.5"')
    assert artifact.filename.endswith(f"breakdown-v{revision.number.value}.json")


def test_real_composition_commits_a_requirement_and_its_projections() -> None:
    from smb_requirement_agent.application.ports.activity import ActivityQuery
    from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
    from smb_requirement_agent.infrastructure.config.settings import Settings
    from smb_requirement_agent.interfaces.api.container import build_container

    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    container = build_container(
        Settings(
            llm_provider=LLMProvider.FAKE,
            persistence_provider=PersistenceProvider.POSTGRES,
            database_url=DATABASE_URL,
        )
    )
    requirement_id = RequirementId(str(uuid.uuid4()))
    try:
        with container.transaction_manager.transaction():
            container.requirement_repository.add(
                Requirement(
                    requirement_id,
                    RequirementTitle("Real projection composition"),
                    RequirementDescription("Commit must include activity and worklist rows."),
                    RequirementStatus.DRAFT,
                )
            )
        result = container.activity_reader.query(ActivityQuery(requirement_id=requirement_id))
        assert result.total == 1
        assert result.items[0].action.value == "requirement_created"
        assert container.requirement_repository.get(requirement_id) is not None
    finally:
        container.close_resources()
        container.debug_trace.close()


def test_generated_quality_and_checked_preview_survive_real_container_restart() -> None:
    from fastapi.testclient import TestClient

    from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
    from smb_requirement_agent.infrastructure.config.settings import Settings
    from smb_requirement_agent.interfaces.api.container import build_container
    from smb_requirement_agent.interfaces.api.main import create_app
    from tests.unit.workflow_helpers import generate_story_tree

    assert DATABASE_URL is not None
    settings = Settings(
        llm_provider=LLMProvider.FAKE,
        persistence_provider=PersistenceProvider.POSTGRES,
        database_url=DATABASE_URL,
    )
    first = build_container(settings)
    with TestClient(create_app(lambda: first)) as client:
        requirement_id, feature_id, stories = generate_story_tree(client)
        path = f"/requirements/{requirement_id}/features/{feature_id}/stories"
        quality = client.get(f"{path}/quality-assessment").json()
        assert quality["fresh"]
        assert len(quality["stories"]) == len(stories)
        assert all(item["architecture"] is not None for item in stories)
        review = client.get(f"/requirements/{requirement_id}/breakdown-review").json()
        assert review["fresh"]
        created = client.post(
            f"{path}/change-proposals",
            json={
                "operation": "split",
                "source_story_ids": [stories[0]["id"]],
                "context_token": client.get(path).json()["generation_context_token"],
            },
        )
        assert created.status_code == 201, created.text
        proposal = created.json()
    second = build_container(settings)
    with TestClient(create_app(lambda: second)) as client:
        assert client.get(f"{path}/quality-assessment").json() == quality
        assert client.get(f"/requirements/{requirement_id}/breakdown-review").json() == review
        assert client.get(f"{path}/change-proposals").json() == [proposal]
        applied = client.post(
            f"{path}/change-proposals/{proposal['id']}/application",
            json={
                "expected_version": proposal["version"],
                "expected_set_version": client.get(path).json()["set_version"],
            },
        )
        assert applied.status_code == 200, applied.text
        final_quality = client.get(f"{path}/quality-assessment").json()
        assert final_quality["fresh"]
        assert len(final_quality["stories"]) == len(applied.json()["stories"])
        assert client.get(f"/requirements/{requirement_id}/breakdown-review").json()["fresh"]


def test_incremental_activity_matches_audit_sources_and_report_aggregation() -> None:
    from smb_requirement_agent.application.use_cases.activity_reporting import (
        aggregate_activity_events,
    )
    from smb_requirement_agent.application.use_cases.create_requirement import (
        CreateRequirementInput,
    )
    from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
    from smb_requirement_agent.infrastructure.config.settings import Settings
    from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
    from smb_requirement_agent.infrastructure.persistence.postgres_activity_reader import (
        PostgresActivityReadAdapter,
    )
    from smb_requirement_agent.infrastructure.persistence.postgres_activity_sources import (
        PostgresActivitySources,
    )
    from smb_requirement_agent.infrastructure.persistence.postgres_repositories import (
        PostgresAnalysisAuditRepository,
    )
    from smb_requirement_agent.infrastructure.persistence.postgres_revisions import (
        PostgresRevisionRepository,
    )
    from smb_requirement_agent.infrastructure.persistence.postgres_snapshots import (
        PostgresSnapshotReader,
    )
    from smb_requirement_agent.interfaces.api.container import build_container

    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    container = build_container(
        Settings(
            llm_provider=LLMProvider.FAKE,
            persistence_provider=PersistenceProvider.POSTGRES,
            database_url=DATABASE_URL,
        )
    )
    try:
        requirement = container.create_requirement.execute(
            CreateRequirementInput(
                title="Incremental activity regression",
                description="Let SMB customers review a connectivity order before submission.",
            ),
            FAKE_ACTORS[0],
        )
        container.analyze_requirement.execute(FAKE_ACTORS[0], requirement.id)
        # A second independent commit must retain the first round's events.
        container.requirement_access.assign_reviewer(
            requirement.id,
            FAKE_ACTORS[0],
            FAKE_ACTORS[1].id,
            container.requirement_access.requirement_view(
                requirement.id, FAKE_ACTORS[0]
            ).access.version,
        )
        session = PostgresStore(DATABASE_URL)
        source = PostgresActivityReadAdapter(
            PostgresActivitySources(
                session, PostgresSnapshotReader(session), PostgresRevisionRepository(session)
            ),
            PostgresAiJobStore(session),
            PostgresRequirementKnowledgeStore(session),
            PostgresAnalysisAuditRepository(session),
        )
        expected = source.list_events_for_requirement(requirement.id)
        actual = container.activity_reader.list_events_for_requirement(requirement.id)
        assert {(event.id, event.action, event.occurred_at) for event in actual} == {
            (event.id, event.action, event.occurred_at) for event in expected
        }
        start = min(event.occurred_at for event in actual) - timedelta(seconds=1)
        before = datetime.now(UTC) + timedelta(seconds=1)
        window = container.activity_reader.window_events(start, before)
        expected_report = aggregate_activity_events(window)
        actual_report = container.activity_reader.aggregate_report(start, before)
        assert set(actual_report.weekly) == set(expected_report.weekly)
        assert actual_report.opened_ids == expected_report.opened_ids
        assert actual_report.resolved_ids == expected_report.resolved_ids
        assert actual_report.median_resolution_hours == expected_report.median_resolution_hours
    finally:
        container.close_resources()
        container.debug_trace.close()


def test_isolated_embedding_generations_resume_switch_and_rollback() -> None:
    from smb_requirement_agent.application.errors import ModelTransportError
    from smb_requirement_agent.infrastructure.persistence import postgres_knowledge_generations

    assert DATABASE_URL is not None
    store = PostgresStore(DATABASE_URL)
    requirement_id = RequirementId(str(uuid.uuid4()))
    store.add(
        Requirement(
            requirement_id,
            RequirementTitle("Index generation test"),
            RequirementDescription("Business customers check coverage."),
            RequirementStatus.DRAFT,
        )
    )
    generations = postgres_knowledge_generations.PostgresKnowledgeIndexGenerations(store)
    first = generations.begin_rebuild("embedding-old")
    assert generations.begin_rebuild("embedding-old").id == first.id
    index = generations.staging_index(first.id)
    assert index.pending_sources(1)
    change = index.pending_sources(1)[0][1]
    chunk = KnowledgeChunk(
        KnowledgeChunkId("source-chunk"),
        requirement_id,
        1,
        KnowledgeSourceKind.SOURCE,
        "business_need",
        "Customers check coverage.",
        "chunk-fingerprint",
        f"/requirements/{requirement_id.value}/capture",
    )
    vector = (1.0, *((0.0,) * 767))
    assert index.replace_if_current(requirement_id, change, "old-fingerprint", (chunk,), (vector,))
    generations.activate(first.id)
    reopened = postgres_knowledge_generations.PostgresKnowledgeIndexGenerations(
        PostgresStore(DATABASE_URL)
    )
    assert reopened.active_index("embedding-old").get_chunks(("source-chunk",)) == (chunk,)
    assert reopened.active_index("embedding-old").search(
        "coverage", vector, RequirementId("other"), 3
    )
    second = reopened.begin_rebuild("embedding-new")
    replacement = reopened.staging_index(second.id)
    assert reopened.begin_rebuild("embedding-new").id == second.id
    with pytest.raises(ModelTransportError):
        reopened.active_index("embedding-new").pending_sources(1)
    with pytest.raises(ModelTransportError):
        reopened.activate(second.id)
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            "UPDATE requirements SET updated_at=now() WHERE requirement_id=%s",
            (requirement_id.value,),
        )
    assert not replacement.replace_if_current(requirement_id, change, "stale", (chunk,), (vector,))
    current_change = replacement.pending_sources(1)[0][1]
    assert replacement.replace_if_current(
        requirement_id, current_change, "new-fingerprint", (chunk,), (vector,)
    )
    reopened.activate(second.id)
    assert (
        reopened.active_index("embedding-new").indexed_fingerprint(requirement_id)
        == "new-fingerprint"
    )
    with pytest.raises(ModelTransportError):
        reopened.activate(first.id)
    assert index.replace_if_current(
        requirement_id, current_change, "updated-old", (chunk,), (vector,)
    )
    reopened.activate(first.id)
    assert (
        reopened.active_index("embedding-old").indexed_fingerprint(requirement_id) == "updated-old"
    )
    assert [item.status for item in reopened.list_generations()] == ["active", "retired"]


def test_requirement_index_batches_survive_restart_and_stale_leases_are_fenced() -> None:
    from smb_requirement_agent.application.use_cases.create_requirement import (
        CreateRequirementInput,
    )
    from smb_requirement_agent.application.use_cases.requirement_indexing import (
        IndexRequirementKnowledge,
    )
    from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
    from smb_requirement_agent.infrastructure.config.settings import Settings
    from smb_requirement_agent.infrastructure.persistence.requirement_indexing import (
        PostgresRequirementIndexProgress,
    )
    from smb_requirement_agent.interfaces.api.container import build_container
    from tests.unit.test_requirement_indexing import RecordingEmbedding, corpus

    assert DATABASE_URL is not None
    container = build_container(
        Settings(
            llm_provider=LLMProvider.FAKE,
            persistence_provider=PersistenceProvider.POSTGRES,
            database_url=DATABASE_URL,
        )
    )
    try:
        requirement = container.create_requirement.execute(
            CreateRequirementInput(
                title="Long field", description="".join(f"{i}:" + "ع" * 500 for i in range(30))
            ),
            FAKE_ACTORS[0],
        )
        progress = PostgresRequirementIndexProgress(PostgresStore(DATABASE_URL))
        embeddings = RecordingEmbedding()
        indexer = IndexRequirementKnowledge(
            corpus(container),
            container.knowledge_index,
            embeddings,
            progress,
            container.clock,
            "A",
            container.requirement_access,
        )
        assert indexer.process_next()
        assert container.knowledge_index.indexed_fingerprint(requirement.id) is None
        reopened = PostgresRequirementIndexProgress(PostgresStore(DATABASE_URL))
        assert reopened.get("A", requirement.id.value) == progress.get("A", requirement.id.value)
        restarted = IndexRequirementKnowledge(
            corpus(container),
            container.knowledge_index,
            embeddings,
            reopened,
            container.clock,
            "A",
            container.requirement_access,
        )
        while restarted.process_next():
            pass
        assert restarted.ready()
        assert all(len(batch) <= 16 for batch in embeddings.calls)
        assert len([text for batch in embeddings.calls for text in batch]) == len(
            set(text for batch in embeddings.calls for text in batch)
        )
        now = container.clock.now()
        first = reopened.claim("B", requirement.id.value, 1, "old", now, now + timedelta(seconds=1))
        assert first
        assert (
            reopened.claim("B", requirement.id.value, 1, "racer", now, now + timedelta(minutes=1))
            is None
        )
        later = now + timedelta(seconds=2)
        assert reopened.claim(
            "B", requirement.id.value, 2, "new", later, later + timedelta(minutes=1)
        )
        assert not progress.save("B", requirement.id.value, "old", first, later)
    finally:
        container.close_resources()
        container.debug_trace.close()
