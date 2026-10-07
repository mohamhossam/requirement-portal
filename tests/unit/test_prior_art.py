"""Prior art from historic requirements (Knowledge Center E2, ADR-0102).

Informational only: a check never adds a finding, never changes knowledge readiness and
never appears in finding counts. It runs after everything else waiting, within an hourly
budget, and only when an operator has turned it on.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from smb_requirement_agent.application.errors import KnowledgeGenerationError
from smb_requirement_agent.application.ports.prior_art import (
    PriorArtCandidateInput,
    PriorArtJudgement,
)
from smb_requirement_agent.application.prior_art_evaluation import (
    PriorArtCase,
    evaluate_prior_art,
)
from smb_requirement_agent.application.use_cases.prior_art import _validated
from smb_requirement_agent.domain.knowledge.prior_art import PriorArtStatus
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.jobs.prior_art_gate import PriorArtGatedQueue
from smb_requirement_agent.infrastructure.jobs.requirement_index_worker import IndexReadyJobQueue
from smb_requirement_agent.infrastructure.llm.fake_requirement_knowledge import FakePriorArtJudge
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.jobs.domain.entities import AiJobOperation, AiJobStatus
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirementInput,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from tests.knowledge_doubles import (
    PublishedLibrary,
    container_with_library,
    index_historic,
    sync,
    work_item,
)
from tests.unit.workflow_helpers import drain_requirement_index

WORKER = "prior-art-test-worker"
EVALUATION = Path(__file__).resolve().parents[2] / "docs/evaluation/prior-art-synthetic.json"
TOKEN = "k" * 40
SERVICE = {"Authorization": f"Bearer {TOKEN}"}

XGPON_BACKLOG = (
    work_item(48213, "epic", "XGPON fibre bundles for small offices"),
    work_item(48214, "feature", "Order an XGPON fibre bundle in BCRM", parent_id=48213),
    work_item(
        48216,
        "user_story",
        "As a sales agent, I choose an XGPON fibre bundle for a small office",
        parent_id=48214,
        description="Only covered addresses offer the fibre bundle.",
    ),
)


def _served(
    *, enabled: bool = True, hourly: int = 60, token: str | None = None
) -> tuple[Container, PublishedLibrary]:
    return container_with_library(
        Settings(
            llm_provider=LLMProvider.FAKE,
            prior_art_enabled=enabled,
            prior_art_judge_calls_per_hour=hourly,
            knowledge_service_token=token,
        )
    )


def _publish_xgpon(container: Container, library: PublishedLibrary) -> str:
    historic_id = library.publish_historic(
        "BRD-2025-014 XGPON bundles",
        ["Business customers order XGPON fibre bundles for small offices through BCRM."],
        XGPON_BACKLOG,
    )
    sync(container)
    index_historic(container)
    return historic_id


def _create(container: Container, title: str, description: str) -> Requirement:
    return container.create_requirement.execute(
        CreateRequirementInput(title=title, description=description), FAKE_ACTORS[0]
    )


def _queue(container: Container) -> IndexReadyJobQueue:
    settings = container.settings
    return IndexReadyJobQueue(
        PriorArtGatedQueue(
            container.ai_job_queue,
            container.prior_art_store,
            container.clock,
            enabled=settings.prior_art_enabled,
            hourly=settings.prior_art_judge_calls_per_hour,
        ),
        container.requirement_indexer,
    )


def _drain(container: Container) -> list[AiJobOperation]:
    """Run every claimable job, as an idle worker would; return what ran, in order."""
    ran: list[AiJobOperation] = []
    queue = _queue(container)
    for _ in range(100):
        drain_requirement_index(container)
        now = container.clock.now()
        claimed = queue.claim_next(WORKER, now, now + timedelta(minutes=5))
        if claimed is None:
            return ran
        ran.append(claimed.job.operation)
        container.execute_ai_job.execute(claimed)
    raise AssertionError("The queue never drained.")


def _prior_art_jobs(container: Container, requirement: Requirement) -> list[AiJobStatus]:
    return [
        record.job.status
        for record in container.ai_job_repository.list_for_requirement(requirement.id)
        if record.job.operation is AiJobOperation.SCREEN_PRIOR_ART
    ]


def test_it_is_off_until_an_operator_turns_it_on() -> None:
    container, library = _served(enabled=False)
    _publish_xgpon(container, library)
    requirement = _create(container, "XGPON bundles", "Small offices order XGPON fibre bundles.")
    _drain(container)
    assert _prior_art_jobs(container, requirement) == []
    assert container.get_prior_art.execute(requirement.id).status is PriorArtStatus.DISABLED


def test_with_no_historic_knowledge_nothing_is_queued() -> None:
    container, _ = _served()
    requirement = _create(container, "XGPON bundles", "Small offices order XGPON fibre bundles.")
    _drain(container)
    assert _prior_art_jobs(container, requirement) == []
    view = container.get_prior_art.execute(requirement.id)
    assert view.status is PriorArtStatus.NO_HISTORIC_KNOWLEDGE


def test_a_similar_past_requirement_is_found_after_everything_else_and_changes_nothing() -> None:
    container, library = _served()
    historic_id = _publish_xgpon(container, library)
    requirement = _create(
        container,
        "XGPON fibre bundles for small offices",
        "Sales agents order XGPON fibre bundles for small offices through BCRM.",
    )
    ran = _drain(container)
    # The screen runs first; prior art waits behind it.
    assert ran.index(AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE) < ran.index(
        AiJobOperation.SCREEN_PRIOR_ART
    )
    view = container.get_prior_art.execute(requirement.id)
    assert view.status is PriorArtStatus.CURRENT and view.check is not None
    (match,) = view.check.matches
    assert match.historic_requirement_id == historic_id and match.publication == 1
    assert match.rationale and match.evidence
    assert view.check.provenance.prompt_version == "prior-art-v1"
    # Informational only: the knowledge review and the corpus counts are as they were.
    review = container.get_knowledge_review.execute(requirement.id)
    assert review.findings == () and review.ready
    assert container.internal_reads.corpus_summary().open_findings.over_30_days == 0


def test_a_withdrawal_hides_the_match_and_a_new_publication_makes_it_out_of_date() -> None:
    container, library = _served()
    historic_id = _publish_xgpon(container, library)
    requirement = _create(
        container,
        "XGPON fibre bundles for small offices",
        "Sales agents order XGPON fibre bundles for small offices through BCRM.",
    )
    _drain(container)
    library.publish_historic(
        "BRD-2025-007 Gulf roaming", ["Prepaid customers buy roaming packs for the Gulf."]
    )
    sync(container)
    index_historic(container)
    view = container.get_prior_art.execute(requirement.id)
    assert view.status is PriorArtStatus.OUT_OF_DATE and view.check is not None
    # Opening the Knowledge step checks again.
    container.knowledge_scheduler.ensure(requirement.id)
    _drain(container)
    assert container.get_prior_art.execute(requirement.id).status is PriorArtStatus.CURRENT
    library.withdraw_historic(historic_id)
    sync(container)
    view = container.get_prior_art.execute(requirement.id)
    assert view.check is not None and view.check.matches == ()


def test_the_hourly_budget_holds_checks_back_without_failing_them() -> None:
    container, library = _served(hourly=1)
    _publish_xgpon(container, library)
    first = _create(
        container, "XGPON fibre bundles", "Sales agents order XGPON fibre bundles for offices."
    )
    second = _create(
        container, "XGPON fibre for shops", "Shops order XGPON fibre bundles through BCRM."
    )
    _drain(container)
    statuses = {
        requirement.id: container.get_prior_art.execute(requirement.id).status
        for requirement in (first, second)
    }
    assert sorted(statuses.values()) == sorted([PriorArtStatus.CURRENT, PriorArtStatus.WAITING])
    waiting = next(rid for rid, status in statuses.items() if status is PriorArtStatus.WAITING)
    assert AiJobStatus.QUEUED in [
        record.job.status
        for record in container.ai_job_repository.list_for_requirement(waiting)
        if record.job.operation is AiJobOperation.SCREEN_PRIOR_ART
    ]


class _WanderingJudge:
    model = "wandering"
    prompt_version = "prior-art-v1"

    def judge(
        self, title: str, subject_text: str, candidates: tuple[PriorArtCandidateInput, ...]
    ) -> tuple[PriorArtJudgement, ...]:
        # Cites evidence it was never shown.
        return (PriorArtJudgement(candidates[0].number, "Alike.", (999,)),)


def test_a_judge_citing_what_it_was_not_shown_fails_the_check_once() -> None:
    container, library = _served()
    _publish_xgpon(container, library)
    screen = container.execute_ai_job._screen_prior_art  # noqa: SLF001
    assert screen is not None
    screen._judge = _WanderingJudge()  # noqa: SLF001
    requirement = _create(
        container,
        "XGPON fibre bundles for small offices",
        "Sales agents order XGPON fibre bundles for small offices through BCRM.",
    )
    _drain(container)
    assert container.get_prior_art.execute(requirement.id).status is PriorArtStatus.FAILED
    # The same key is not queued again: no repeated spend on a failing judge.
    container.knowledge_scheduler.ensure(requirement.id)
    assert _prior_art_jobs(container, requirement).count(AiJobStatus.QUEUED) == 0
    # A candidate it was never shown is refused the same way.
    with pytest.raises(KnowledgeGenerationError):
        _validated((PriorArtJudgement(9, "x", (1,)),), (), {})


def test_the_knowledge_portal_reads_where_each_historic_requirement_is_cited() -> None:
    container, library = _served(token=TOKEN)
    historic_id = _publish_xgpon(container, library)
    requirement = _create(
        container,
        "XGPON fibre bundles for small offices",
        "Sales agents order XGPON fibre bundles for small offices through BCRM.",
    )
    _drain(container)
    with TestClient(create_app(lambda: container)) as client:
        counts = client.get(
            "/internal/knowledge/historic/citation-counts",
            params=[("historic_id", historic_id), ("historic_id", "other")],
            headers=SERVICE,
        )
        assert counts.json() == {"counts": {historic_id: 1, "other": 0}}
        page = client.get(
            f"/internal/knowledge/historic/{historic_id}/citations", headers=SERVICE
        ).json()
        (item,) = page["items"]
        assert item["requirement_id"] == requirement.id.value and item["current"] is True
        assert set(item) == {
            "requirement_id",
            "title",
            "owner",
            "checked_at",
            "current",
            "retired",
            "duplicate",
        }
        assert client.get("/internal/knowledge/historic/citation-counts").status_code in {
            401,
            422,
        }
        too_many: list[tuple[str, str | int | float | bool | None]] = [
            ("historic_id", f"h{n}") for n in range(101)
        ]
        assert (
            client.get(
                "/internal/knowledge/historic/citation-counts", params=too_many, headers=SERVICE
            ).status_code
            == 422
        )
        # The browser's read of the same Requirement's prior art.
        public = client.get(f"/requirements/{requirement.id.value}/prior-art").json()
        assert public["status"] == "current" and public["label"] == "historic"
        passage_kinds = {p["source_kind"] for p in public["matches"][0]["passages"]}
        assert passage_kinds <= {"historic_brd", "historic_backlog"}


def test_the_fake_judge_passes_the_evaluation_gates_on_the_synthetic_cases() -> None:
    cases = TypeAdapter(tuple[PriorArtCase, ...]).validate_json(EVALUATION.read_text())
    result = evaluate_prior_art(cases, FakePriorArtJudge())
    assert result.pairs >= 24 and result.invalid_citations == 0
    assert result.quality_gate_passed, result
    # A judge that calls everything similar fails on the near misses.

    class _Eager:
        model = "eager"
        prompt_version = "prior-art-v1"

        def judge(
            self, title: str, subject_text: str, candidates: tuple[PriorArtCandidateInput, ...]
        ) -> tuple[PriorArtJudgement, ...]:
            return tuple(
                PriorArtJudgement(c.number, "Same topic.", (c.evidence[0].number,))
                for c in candidates
            )

    assert not evaluate_prior_art(cases, _Eager()).quality_gate_passed
