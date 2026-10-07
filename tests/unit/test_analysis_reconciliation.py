"""A re-analysis must account for every active AI question, or it is refused.

`reconcile_round` is pure, so each rule is tested directly. The baseline is a
real second-round candidate from the fake analyzer, which retains every
question. Each test breaks one rule the way a misbehaving model could.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from smb_requirement_agent.application.errors import RequirementAnalysisGenerationError
from smb_requirement_agent.application.ports.requirement_analyzer import (
    ActiveQuestionContext,
    RequirementAnalysisCandidate,
    UncertaintyCandidate,
)
from smb_requirement_agent.application.use_cases.analysis_mapping import build_analysis
from smb_requirement_agent.application.use_cases.analysis_reconciliation import reconcile_round
from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirementInput
from smb_requirement_agent.domain.analysis.entities import (
    ClarificationQuestion,
    RequirementAnalysis,
)
from smb_requirement_agent.domain.analysis.value_objects import (
    AnalysisId,
    ClarificationKind,
    ClarificationSource,
    QuestionChangeAction,
    QuestionId,
)
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.llm.fake_requirement_analyzer import (
    FakeRequirementAnalyzer,
)
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.shared_kernel.generation import Provenance
from tests.conftest import FAKE_PROVIDER_SETTINGS

Round = tuple[RequirementAnalysis, RequirementAnalysisCandidate, tuple[ClarificationQuestion, ...]]


@pytest.fixture
def second_round() -> Round:
    container = build_container(FAKE_PROVIDER_SETTINGS)
    requirement = container.create_requirement.execute(
        CreateRequirementInput("Refunds", "Refund within five business days."), FAKE_ACTORS[0]
    )
    container.analyze_requirement.execute(FAKE_ACTORS[0], requirement.id)
    active = tuple(
        item
        for item in container.analysis_audit_repository.list_questions(requirement.id)
        if item.is_active
    )
    candidate = FakeRequirementAnalyzer().analyze(
        requirement,
        (),
        (),
        (),
        tuple(
            ActiveQuestionContext(
                question_id=item.id.value,
                kind=item.kind,
                subject=item.subject,
                rationale=item.rationale,
                source=item.source,
            )
            for item in active
        ),
    )
    analysis = build_analysis(
        requirement.id,
        candidate,
        (),
        (),
        analysis_id=AnalysisId("analysis-2"),
        round_number=2,
        provenance=Provenance(datetime.now(UTC), "fake", "v1"),
        source_requirement_version=requirement.version,
        version=2,
    )
    return analysis, candidate, active


def _refused(
    round_: Round, change: Callable[[RequirementAnalysisCandidate], None], message: str
) -> None:
    analysis, candidate, active = round_
    broken = copy.deepcopy(candidate)
    change(broken)
    with pytest.raises(RequirementAnalysisGenerationError, match=message):
        reconcile_round(analysis, broken, active)


def test_a_complete_review_retains_every_question(second_round: Round) -> None:
    analysis, candidate, active = second_round

    reconciled = reconcile_round(analysis, candidate, active)

    assert len(active) == 4
    assert {item.action for item in reconciled.round.question_changes} == {
        QuestionChangeAction.RETAINED
    }
    assert set(reconciled.round.question_ids) == {item.id for item in active}
    assert reconciled.new_questions == () and reconciled.superseded_questions == ()


def test_every_active_ai_question_must_be_reviewed(second_round: Round) -> None:
    def drop_one(candidate: RequirementAnalysisCandidate) -> None:
        candidate["question_reviews"] = candidate["question_reviews"][:-1]

    _refused(second_round, drop_one, "did not reconcile every active AI")


def test_reconciliation_details_cannot_be_omitted(second_round: Round) -> None:
    def omit(candidate: RequirementAnalysisCandidate) -> None:
        del candidate["new_uncertainties"]

    _refused(second_round, omit, "omitted reconciliation details")


@pytest.mark.parametrize(
    ("action", "with_replacement", "message"),
    [
        (QuestionChangeAction.RETAINED, True, "retained question cannot include"),
        (QuestionChangeAction.RETIRED, True, "retired question cannot include"),
        (QuestionChangeAction.REPLACED, False, "requires valid replacement"),
    ],
)
def test_each_action_carries_exactly_the_content_it_needs(
    second_round: Round, action: QuestionChangeAction, with_replacement: bool, message: str
) -> None:
    def rewrite(candidate: RequirementAnalysisCandidate) -> None:
        review = candidate["question_reviews"][0]
        review["action"] = action
        review["replacement"] = (
            UncertaintyCandidate(
                kind=ClarificationKind.OPEN_QUESTION, subject="New?", rationale="Why."
            )
            if with_replacement
            else None
        )

    _refused(second_round, rewrite, message)


def test_a_new_uncertainty_cannot_duplicate_a_retained_question(second_round: Round) -> None:
    _, _, active = second_round
    first = active[0]

    def duplicate(candidate: RequirementAnalysisCandidate) -> None:
        candidate["new_uncertainties"] = [
            UncertaintyCandidate(kind=first.kind, subject=first.subject, rationale="Again.")
        ]

    _refused(second_round, duplicate, "duplicate reconciled uncertainties")


def test_retiring_a_question_the_analysis_still_states_is_refused(second_round: Round) -> None:
    def retire(candidate: RequirementAnalysisCandidate) -> None:
        candidate["question_reviews"][0]["action"] = QuestionChangeAction.RETIRED

    _refused(second_round, retire, "do not match the replacement analysis")


def test_the_model_cannot_restate_a_question_a_person_asked(second_round: Round) -> None:
    analysis, candidate, active = second_round
    human = replace(active[0], id=QuestionId("human-1"), source=ClarificationSource.HUMAN)

    with pytest.raises(RequirementAnalysisGenerationError, match="protected human"):
        reconcile_round(analysis, candidate, (*active, human))
