"""Reconcile an analyzer's question reviews into the next analysis round.

A re-analysis must account for every active AI clarification question:
retained, retired or replaced, each with a reason. It may add new
uncertainties, but never duplicate one, nor restate a question a person
asked. This checks the model's output against those rules and builds the round.
It is pure: storing the round is the caller's job.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    QuestionReviewCandidate,
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.analysis.domain.entities import (
    AnalysisQuestionChange,
    AnalysisRound,
    ClarificationQuestion,
    RequirementAnalysis,
)
from smb_requirement_agent.analysis.domain.value_objects import (
    ClarificationKind,
    ClarificationSeverity,
    ClarificationSource,
    QuestionChangeAction,
    QuestionId,
)
from smb_requirement_agent.application.errors import RequirementAnalysisGenerationError


@dataclass(frozen=True)
class ReconciledRound:
    round: AnalysisRound
    new_questions: tuple[ClarificationQuestion, ...]
    superseded_questions: tuple[ClarificationQuestion, ...]


def reconcile_round(
    analysis: RequirementAnalysis,
    candidate: RequirementAnalysisCandidate,
    previous_active: tuple[ClarificationQuestion, ...],
) -> ReconciledRound:
    if analysis.id is None:  # pragma: no cover - build invariant
        raise AssertionError("Prepared analysis must have an identity.")
    analysis_id = analysis.id
    active_by_id = {item.id.value: item for item in previous_active}
    ai_ids = {item.id.value for item in previous_active if item.source is ClarificationSource.AI}
    reviews = candidate.get("question_reviews", [])
    if {item["question_id"] for item in reviews} != ai_ids or len(reviews) != len(ai_ids):
        raise RequirementAnalysisGenerationError(
            "Analyzer did not reconcile every active AI clarification question."
        )

    questions_by_key: dict[tuple[ClarificationKind, str], ClarificationQuestion] = {}
    changes: list[AnalysisQuestionChange] = []
    new_questions: list[ClarificationQuestion] = []
    superseded_questions: list[ClarificationQuestion] = []
    for review in reviews:
        _apply_question_review(
            analysis,
            review,
            active_by_id,
            questions_by_key,
            changes,
            new_questions,
            superseded_questions,
        )

    new_uncertainties = candidate.get("new_uncertainties")
    if new_uncertainties is None:
        if ai_ids:
            raise RequirementAnalysisGenerationError(
                "Analyzer omitted reconciliation details for active AI questions."
            )
        new_uncertainties = [
            {
                "kind": kind,
                "subject": subject,
                "rationale": rationale,
            }
            for kind, subject, rationale in analysis_uncertainties(analysis)
        ]
    for item in new_uncertainties:
        question = ClarificationQuestion(
            QuestionId(str(uuid.uuid4())),
            analysis.requirement_id,
            analysis_id,
            item["kind"],
            item["subject"],
            item["rationale"],
            ClarificationSeverity.MEDIUM,
            True,
            ClarificationSource.AI,
        )
        key = question.key
        if key in questions_by_key:
            raise RequirementAnalysisGenerationError(
                "Analyzer returned duplicate reconciled uncertainties."
            )
        questions_by_key[key] = question
        new_questions.append(question)
        changes.append(
            AnalysisQuestionChange(
                QuestionChangeAction.CREATED,
                question.id,
                item["rationale"] or "A new uncertainty was identified during analysis.",
            )
        )

    expected_keys = [
        (kind, subject.casefold()) for kind, subject, _ in analysis_uncertainties(analysis)
    ]
    if set(questions_by_key) != set(expected_keys) or len(expected_keys) != len(set(expected_keys)):
        raise RequirementAnalysisGenerationError(
            "Analyzer question reviews do not match the replacement analysis."
        )

    human_questions = [item for item in previous_active if item.source is ClarificationSource.HUMAN]
    current_subjects = [key[1] for key in questions_by_key]
    protected_subjects = {item.subject.casefold() for item in human_questions}
    if len(current_subjects) != len(set(current_subjects)) or protected_subjects.intersection(
        current_subjects
    ):
        raise RequirementAnalysisGenerationError(
            "Analyzer duplicated a current or protected human clarification question."
        )
    round_questions = [
        *human_questions,
        *(questions_by_key[key] for key in expected_keys),
    ]
    return ReconciledRound(
        AnalysisRound(
            analysis,
            tuple(item.id for item in round_questions),
            tuple(changes),
        ),
        tuple(new_questions),
        tuple(superseded_questions),
    )


def analysis_uncertainties(
    analysis: RequirementAnalysis,
) -> tuple[tuple[ClarificationKind, str, str | None], ...]:
    """Every uncertainty an analysis states, as (kind, subject, rationale)."""
    return (
        *((ClarificationKind.ASSUMPTION, item.statement, None) for item in analysis.assumptions),
        *(
            (ClarificationKind.OPEN_QUESTION, item.question, item.rationale)
            for item in analysis.open_questions
        ),
        *(
            (ClarificationKind.AMBIGUITY, item.statement, item.reason)
            for item in analysis.ambiguities
        ),
        *(
            (ClarificationKind.POTENTIAL_DEPENDENCY, item.statement, None)
            for item in analysis.potential_dependencies
        ),
    )


def _apply_question_review(
    analysis: RequirementAnalysis,
    review: QuestionReviewCandidate,
    active_by_id: dict[str, ClarificationQuestion],
    questions_by_key: dict[tuple[ClarificationKind, str], ClarificationQuestion],
    changes: list[AnalysisQuestionChange],
    new_questions: list[ClarificationQuestion],
    superseded_questions: list[ClarificationQuestion],
) -> None:
    if analysis.id is None:  # pragma: no cover - guarded by caller
        raise AssertionError("Reconciliation requires an identified analysis.")
    original = active_by_id.get(review["question_id"])
    if original is None or original.source is not ClarificationSource.AI:
        raise RequirementAnalysisGenerationError(
            "Analyzer reviewed an unknown or human-authored clarification question."
        )
    action = review["action"]
    replacement = review["replacement"]
    if action is QuestionChangeAction.RETAINED:
        if replacement is not None:
            raise RequirementAnalysisGenerationError(
                "A retained question cannot include replacement content."
            )
        if original.key in questions_by_key:
            raise RequirementAnalysisGenerationError(
                "Analyzer returned duplicate reconciled uncertainties."
            )
        questions_by_key[original.key] = original
        changes.append(AnalysisQuestionChange(action, original.id, review["rationale"]))
        return
    if action is QuestionChangeAction.RETIRED:
        if replacement is not None:
            raise RequirementAnalysisGenerationError(
                "A retired question cannot include replacement content."
            )
        superseded_questions.append(original.supersede())
        changes.append(AnalysisQuestionChange(action, original.id, review["rationale"]))
        return
    if action is not QuestionChangeAction.REPLACED or replacement is None:
        raise RequirementAnalysisGenerationError(
            "A replaced question requires valid replacement content."
        )
    replacement_id = QuestionId(str(uuid.uuid4()))
    question = original.replacement(
        replacement_id,
        analysis.id,
        replacement["kind"],
        replacement["subject"],
        replacement["rationale"],
    )
    if question.key in questions_by_key:
        raise RequirementAnalysisGenerationError(
            "Analyzer returned duplicate reconciled uncertainties."
        )
    questions_by_key[question.key] = question
    superseded_questions.append(original.supersede())
    new_questions.append(question)
    changes.append(
        AnalysisQuestionChange(
            action,
            original.id,
            review["rationale"],
            replacement_id,
        )
    )
