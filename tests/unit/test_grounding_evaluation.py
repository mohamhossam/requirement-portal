"""Synthetic arithmetic fixtures do not certify provider semantics."""

import pytest

from smb_requirement_agent.application.grounding_evaluation import (
    GroundingJudgment,
    evaluate_grounding,
)


def test_semantic_report_counts_support_conflicts_and_abstention_separately() -> None:
    result = evaluate_grounding(
        (
            GroundingJudgment(
                "supported", "synthetic fixture", True, False, True, True, False, None
            ),
            GroundingJudgment(
                "invented", "synthetic fixture", False, False, False, False, True, False
            ),
            GroundingJudgment("abstain", "synthetic fixture", False, True, None, None, True, True),
            GroundingJudgment("missed", "synthetic fixture", True, True, None, None, False, None),
        )
    )
    assert result.supported_answer_rate == 0.5
    assert result.correct_abstention_rate == 0.5
    assert (
        result.unsupported_answers == result.applicability_failures == result.missed_conflicts == 1
    )
    assert result.unnecessary_abstentions == 1


def test_semantic_report_cannot_treat_abstentions_as_supported_answers() -> None:
    judgment = GroundingJudgment("empty", "synthetic fixture", False, True, None, None, False, None)
    assert evaluate_grounding((judgment,)).supported_answer_rate is None
    with pytest.raises(ValueError):
        evaluate_grounding((judgment, judgment))
    with pytest.raises(ValueError):
        GroundingJudgment("bad", "synthetic fixture", True, False, None, None, False, None)
    with pytest.raises(ValueError):
        GroundingJudgment("bad", "", True, False, True, True, False, None)
