"""Dedicated indexing must be bounded, resumable, fenced and observable."""

from datetime import UTC, datetime, timedelta
from threading import RLock

import pytest
from fastapi.testclient import TestClient
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.errors import (
    KnowledgeGenerationError,
    KnowledgeIndexPendingError,
    KnowledgeScreenConflictError,
)
from smb_requirement_agent.application.ports.requirement_indexing import RequirementIndexProgress
from smb_requirement_agent.application.use_cases.requirement_indexing import (
    IndexRequirementKnowledge,
)
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    RequirementKnowledgeCorpus,
    bounded_knowledge_text,
)
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.jobs.requirement_index_worker import IndexReadyJobQueue
from smb_requirement_agent.infrastructure.llm.fake_requirement_knowledge import (
    FakeKnowledgeEmbedding,
)
from smb_requirement_agent.infrastructure.persistence.requirement_indexing import (
    MemoryRequirementIndexProgress,
)
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.jobs.domain.entities import (
    AiJobOperation,
    AiJobStatus,
    NotificationKind,
)
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirementInput,
)
from smb_requirement_agent.requirements.application.use_cases.update_requirement import (
    UpdateRequirementInput,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from tests.unit.workflow_helpers import drain_requirement_index


class RecordingEmbedding(FakeKnowledgeEmbedding):
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.fail = False

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.calls.append(texts)
        if self.fail:
            raise KnowledgeGenerationError("Synthetic provider failure")
        return super().embed(texts)


def corpus(container: Container) -> RequirementKnowledgeCorpus:
    return RequirementKnowledgeCorpus(
        container.requirement_repository,
        container.analysis_repository,
        container.analysis_audit_repository,
        container.access_repository,
        container.knowledge_repository,
        container.document_repository,
    )


def test_long_bilingual_fields_resume_batches_and_never_publish_partial_vectors(
    container: Container,
) -> None:
    text = "".join(f"{i}: التغطية مطلوبة للطلب. " + "x" * 720 for i in range(40))
    requirement = container.create_requirement.execute(
        CreateRequirementInput(title="Coverage", description=text), FAKE_ACTORS[0]
    )
    progress = MemoryRequirementIndexProgress(RLock())
    embeddings = RecordingEmbedding()
    indexer = IndexRequirementKnowledge(
        corpus(container),
        container.knowledge_index,
        embeddings,
        progress,
        container.clock,
        "model-A",
        container.requirement_access,
    )
    assert indexer.process_next()
    assert len(embeddings.calls[0]) == 16
    assert container.knowledge_index.indexed_fingerprint(requirement.id) is None
    saved = progress.get("model-A", requirement.id.value)
    assert saved.completed < saved.total
    restarted = IndexRequirementKnowledge(
        corpus(container),
        container.knowledge_index,
        embeddings,
        progress,
        container.clock,
        "model-A",
        container.requirement_access,
    )
    while restarted.process_next():
        pass
    assert restarted.ready()
    assert all(len(batch) <= 16 for batch in embeddings.calls)
    assert all(len(text.encode()) <= 768 for batch in embeddings.calls for text in batch)
    assert len([t for batch in embeddings.calls for t in batch]) == len(
        set(t for batch in embeddings.calls for t in batch)
    )
    chunks = corpus(container).chunks(requirement)
    assert len({c.id for c in chunks}) == len(chunks)
    assert all(c.field in {"title", "business_need"} for c in chunks)


def test_index_lease_expiry_fences_old_worker_and_model_caches_are_isolated() -> None:
    progress = MemoryRequirementIndexProgress(RLock())
    now = datetime(2026, 9, 22, tzinfo=UTC)
    first = progress.claim("A", "source", 1, "old", now, now + timedelta(seconds=1))
    assert first is not None
    assert progress.claim("A", "source", 1, "racer", now, now + timedelta(seconds=1)) is None
    later = now + timedelta(seconds=2)
    assert progress.claim("A", "source", 2, "new", later, later + timedelta(seconds=10))
    assert not progress.save("A", "source", "old", first, later)
    assert progress.get("B", "source") == RequirementIndexProgress()


def test_failure_backoff_stops_at_three_and_explicit_retry_resumes(container: Container) -> None:
    requirement = container.create_requirement.execute(
        CreateRequirementInput(title="Coverage", description="Coverage required."), FAKE_ACTORS[0]
    )
    clock = FixedClock(datetime(2026, 9, 22, tzinfo=UTC))
    progress = MemoryRequirementIndexProgress(RLock())
    embeddings = RecordingEmbedding()
    embeddings.fail = True
    indexer = IndexRequirementKnowledge(
        corpus(container),
        container.knowledge_index,
        embeddings,
        progress,
        clock,
        "A",
        container.requirement_access,
    )
    for _ in range(3):
        assert indexer.process_next()
        assert not indexer.process_next()
        clock.set(clock.now() + timedelta(minutes=5))
    assert not indexer.process_next()
    assert indexer.status(requirement.id.value, FAKE_ACTORS[0]).state == "failed"
    embeddings.fail = False
    indexer.retry(requirement.id.value, FAKE_ACTORS[0])
    assert indexer.process_next() and indexer.ready()


def test_screening_does_not_embed_the_portfolio_and_queue_waits_for_index(
    container: Container,
) -> None:
    requirement = container.create_requirement.execute(
        CreateRequirementInput(title="Coverage", description="Coverage required."), FAKE_ACTORS[0]
    )
    fingerprint = corpus(container).fingerprint(requirement.id)
    with pytest.raises(KnowledgeIndexPendingError):
        container.screen_requirement_knowledge.execute(FAKE_ACTORS[0], requirement.id, fingerprint)
    queue = IndexReadyJobQueue(container.ai_job_queue, container.requirement_indexer)
    now = container.clock.now()
    assert queue.claim_next("worker", now, now + timedelta(minutes=1)) is None
    drain_requirement_index(container)
    claimed = queue.claim_next("worker", now, now + timedelta(minutes=1))
    assert claimed and claimed.job.operation.value == "screen_requirement_knowledge"


def test_source_created_after_gate_check_requeues_screen_without_failing_or_consuming(
    container: Container, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: ready() passed, then a Requirement appeared before its screen executed."""
    queue = IndexReadyJobQueue(container.ai_job_queue, container.requirement_indexer)
    gate_check = container.requirement_indexer.ready
    observed: list[bool] = []
    created: list[Requirement] = []

    def ready_then_source_appears() -> bool:
        observed.append(gate_check())
        created.append(
            container.create_requirement.execute(
                CreateRequirementInput(title="Coverage", description="Coverage required."),
                FAKE_ACTORS[0],
            )
        )
        return observed[-1]

    monkeypatch.setattr(container.requirement_indexer, "ready", ready_then_source_appears)
    now = container.clock.now()
    lease_until = now + timedelta(minutes=1)
    claimed = queue.claim_next("worker", now, lease_until)
    monkeypatch.undo()

    assert observed == [True]
    assert claimed is not None and claimed.attempt_token is not None
    assert claimed.job.operation is AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE
    assert claimed.job.requirement_id == created[0].id
    assert not container.requirement_indexer.ready()

    deferred = container.execute_ai_job.execute(claimed)

    assert deferred.status is AiJobStatus.QUEUED
    assert deferred.failure is None
    assert deferred.attempt_count == 0
    stored = container.ai_job_repository.get(claimed.job.id)
    assert stored is not None and stored.job == deferred
    assert stored.worker_id is None and stored.attempt_token is None
    assert not any(
        item.kind is NotificationKind.AI_JOB_FAILED
        for item in container.notification_repository.list_for_actor(FAKE_ACTORS[0].id)
    )
    # The deferred attempt is fenced: it can neither heartbeat nor write.
    assert not container.ai_job_queue.heartbeat(
        claimed.job.id, "worker", claimed.attempt_token, now, lease_until
    )
    assert not container.ai_job_repository.save_fenced(
        claimed.job.succeed((), now), "worker", claimed.attempt_token, now
    )
    # The gate holds the job while the index is pending, then it runs normally.
    assert queue.claim_next("worker", now, lease_until) is None
    drain_requirement_index(container)
    retried = queue.claim_next("worker", now, lease_until)
    assert retried is not None and retried.job.id == claimed.job.id
    assert retried.job.attempt_count == 1
    assert container.execute_ai_job.execute(retried).status is AiJobStatus.SUCCEEDED


def test_knowledge_change_during_screening_is_a_conflict_not_a_provider_failure(
    container: Container, monkeypatch: pytest.MonkeyPatch
) -> None:
    requirement = container.create_requirement.execute(
        CreateRequirementInput(title="Coverage", description="Coverage required."), FAKE_ACTORS[0]
    )
    drain_requirement_index(container)
    fingerprint = corpus(container).fingerprint(requirement.id)
    screen = container.screen_requirement_knowledge
    monkeypatch.setattr(screen._corpus, "citations_current", lambda citations: False)
    with pytest.raises(KnowledgeScreenConflictError):
        screen.execute(FAKE_ACTORS[0], requirement.id, fingerprint)
    monkeypatch.undo()
    monkeypatch.setattr(screen._index, "pending_sources", lambda limit: ((requirement.id, 1),))
    with pytest.raises(KnowledgeIndexPendingError):
        screen.execute(FAKE_ACTORS[0], requirement.id, fingerprint)


def test_automatic_screen_defers_when_knowledge_changes_before_commit(
    container: Container, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a Requirement created mid-screen failed the automatic job as a 502."""
    requirement = container.create_requirement.execute(
        CreateRequirementInput(title="Coverage", description="Coverage required."), FAKE_ACTORS[0]
    )
    drain_requirement_index(container)
    queue = IndexReadyJobQueue(container.ai_job_queue, container.requirement_indexer)
    now = container.clock.now()
    lease_until = now + timedelta(minutes=1)
    claimed = queue.claim_next("worker", now, lease_until)
    assert claimed is not None and claimed.job.requirement_id == requirement.id
    monkeypatch.setattr(
        container.screen_requirement_knowledge._corpus,
        "citations_current",
        lambda citations: False,
    )

    deferred = container.execute_ai_job.execute(claimed)
    monkeypatch.undo()

    assert deferred.status is AiJobStatus.QUEUED
    assert deferred.failure is None
    assert deferred.attempt_count == 0
    assert not any(
        item.kind is NotificationKind.AI_JOB_FAILED
        for item in container.notification_repository.list_for_actor(FAKE_ACTORS[0].id)
    )
    retried = queue.claim_next("worker", now, lease_until)
    assert retried is not None and retried.job.id == claimed.job.id
    assert container.execute_ai_job.execute(retried).status is AiJobStatus.SUCCEEDED


def test_source_change_during_embedding_cannot_clear_new_pending_work(container: Container) -> None:
    requirement = container.create_requirement.execute(
        CreateRequirementInput(title="Coverage", description="Coverage required."), FAKE_ACTORS[0]
    )

    class ChangingEmbedding(FakeKnowledgeEmbedding):
        def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
            container.update_requirement.execute(
                FAKE_ACTORS[0],
                requirement.id,
                UpdateRequirementInput(
                    title="Coverage",
                    description="Changed coverage rule.",
                    expected_version=requirement.version.value,
                ),
                impact_acknowledged=True,
            )
            return super().embed(texts)

    indexer = IndexRequirementKnowledge(
        corpus(container),
        container.knowledge_index,
        ChangingEmbedding(),
        MemoryRequirementIndexProgress(RLock()),
        container.clock,
        "A",
        container.requirement_access,
    )
    assert indexer.process_next()
    assert container.knowledge_index.indexed_fingerprint(requirement.id) is None
    assert not indexer.ready()


@pytest.mark.parametrize(
    "text", ["العربية. " * 500, "a" * 4000, "🙂\u200d\n" * 600, " " * 769 + "word"]
)
def test_requirement_chunk_spans_preserve_every_character(text: str) -> None:
    spans = bounded_knowledge_text(text)
    assert "".join(spans) == text
    assert all(0 < len(span.encode()) <= 768 for span in spans)


def test_index_status_and_retry_require_membership(client: TestClient) -> None:
    created = client.post("/requirements", json={"title": "Coverage", "description": "Required."})
    path = f"/requirements/{created.json()['id']}/knowledge-index"
    assert client.get(path).status_code == 200
    assert client.post(f"{path}/retry").status_code == 200
    for method, url in ((client.get, path), (client.post, f"{path}/retry")):
        assert method(url, headers={"X-Fake-Actor-Id": "fake-observer"}).status_code == 403


def test_blocked_first_page_does_not_starve_later_requirements(container: Container) -> None:
    requirements = [
        container.create_requirement.execute(
            CreateRequirementInput(title=f"Source {i}", description=f"Coverage {i}"),
            FAKE_ACTORS[0],
        )
        for i in range(101)
    ]
    ordered = sorted(requirements, key=lambda r: r.id.value)
    progress = MemoryRequirementIndexProgress(RLock())
    now = container.clock.now()
    changes = dict(container.knowledge_index.pending_sources(200))
    for requirement in ordered[:100]:
        assert progress.claim(
            "A",
            requirement.id.value,
            changes[requirement.id],
            "lease",
            now,
            now + timedelta(minutes=1),
        )
        assert progress.save(
            "A",
            requirement.id.value,
            "lease",
            RequirementIndexProgress(source_change=changes[requirement.id], failures=3),
            now,
        )
    indexer = IndexRequirementKnowledge(
        corpus(container),
        container.knowledge_index,
        RecordingEmbedding(),
        progress,
        container.clock,
        "A",
        container.requirement_access,
    )
    assert not indexer.process_next()
    assert indexer.process_next()
    assert container.knowledge_index.indexed_fingerprint(ordered[-1].id)
