"""Small synthetic cases test arithmetic, not production retrieval quality."""

import pytest

from smb_requirement_agent.references.application.retrieval_evaluation import (
    EvaluationQuery,
    QueryResult,
    RetrievedSource,
    SourceJudgment,
    evaluate_retrieval,
)


def test_source_duplicates_do_not_inflate_recall_and_small_sets_cannot_qualify() -> None:
    query = EvaluationQuery(
        "q1", "synthetic-test-only", True, (SourceJudgment("a", 3), SourceJudgment("b", 2))
    )
    results = QueryResult("q1", (RetrievedSource("a", True, True),) * 3)
    report = evaluate_retrieval((query,), (results,))
    assert report.recall_at_20 == 0.5
    assert report.cross_language_recall_at_20 == 0.5
    assert report.hit_rate_at_20 == 1
    assert 0 < report.ndcg_at_10 < 1
    assert not report.quality_gate_passed


def test_leakage_and_invalid_citations_are_counted_even_in_duplicate_excerpts() -> None:
    query = EvaluationQuery("q1", "synthetic-test-only", False, (SourceJudgment("a", 3),))
    result = QueryResult(
        "q1", (RetrievedSource("a", True, True), RetrievedSource("a", False, False))
    )
    report = evaluate_retrieval((query,), (result,))
    assert report.ineligible_sources == report.invalid_citations == 1
    assert not report.quality_gate_passed


def test_missing_results_or_reviewer_cannot_be_reported_as_a_pass() -> None:
    query = EvaluationQuery("q1", "synthetic-test-only", False, (SourceJudgment("a", 1),))
    with pytest.raises(ValueError, match="Exactly one result"):
        evaluate_retrieval((query,), ())
    with pytest.raises(ValueError, match="human reviewer"):
        EvaluationQuery("q", "", False, (SourceJudgment("a", 1),))
