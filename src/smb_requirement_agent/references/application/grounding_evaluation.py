"""Summarize explicit semantic judgments; never infer support from citation presence."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GroundingJudgment:
    case_id: str
    reviewer: str
    answerable: bool
    abstained: bool
    supported: bool | None
    applicability_preserved: bool | None
    conflict_present: bool
    conflict_handled: bool | None

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.reviewer.strip():
            raise ValueError("Each case requires an identity and an explicit reviewer.")
        if self.abstained:
            if self.supported is not None or self.applicability_preserved is not None:
                raise ValueError("Abstentions have no answer support/applicability judgment.")
        elif self.supported is None or self.applicability_preserved is None:
            raise ValueError("Every generated answer needs support and applicability judgments.")
        if self.conflict_present != (self.conflict_handled is not None):
            raise ValueError("Judge conflict handling exactly when conflicting evidence exists.")


@dataclass(frozen=True)
class GroundingEvaluation:
    cases: int
    answered_cases: int
    supported_answers: int
    unsupported_answers: int
    applicability_failures: int
    missed_conflicts: int
    correct_abstentions: int
    unnecessary_abstentions: int
    supported_answer_rate: float | None
    correct_abstention_rate: float | None


def evaluate_grounding(judgments: tuple[GroundingJudgment, ...]) -> GroundingEvaluation:
    if not judgments or len({j.case_id for j in judgments}) != len(judgments):
        raise ValueError("Supply nonempty, uniquely identified semantic judgments.")
    answers = [j for j in judgments if not j.abstained]
    unanswerable = [j for j in judgments if not j.answerable]
    supported = sum(j.supported is True for j in answers)
    correct_abstentions = sum(j.abstained for j in unanswerable)
    return GroundingEvaluation(
        len(judgments),
        len(answers),
        supported,
        len(answers) - supported,
        sum(j.applicability_preserved is False for j in answers),
        sum(j.conflict_handled is False for j in judgments),
        correct_abstentions,
        sum(j.answerable and j.abstained for j in judgments),
        supported / len(answers) if answers else None,
        correct_abstentions / len(unanswerable) if unanswerable else None,
    )
