"""Deterministic source-level retrieval evaluation; never fabricates human judgments."""

from dataclasses import dataclass
from math import log2


@dataclass(frozen=True)
class SourceJudgment:
    source_id: str
    relevance: int

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not 0 <= self.relevance <= 3:
            raise ValueError("Judgments require a source identity and relevance grade 0–3.")


@dataclass(frozen=True)
class EvaluationQuery:
    id: str
    human_reviewer: str
    cross_language: bool
    judgments: tuple[SourceJudgment, ...]

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.human_reviewer.strip():
            raise ValueError("Evaluation requires query identity and an actual human reviewer.")
        if len({j.source_id for j in self.judgments}) != len(self.judgments):
            raise ValueError("Source judgments must be unique within a query.")
        if not any(j.relevance > 0 for j in self.judgments):
            raise ValueError("Quality queries require at least one known relevant source.")


@dataclass(frozen=True)
class RetrievedSource:
    source_id: str
    eligible: bool
    citation_valid: bool


@dataclass(frozen=True)
class QueryResult:
    query_id: str
    sources: tuple[RetrievedSource, ...]


@dataclass(frozen=True)
class RetrievalEvaluation:
    queries: int
    cross_language_queries: int
    recall_at_20: float
    cross_language_recall_at_20: float
    hit_rate_at_20: float
    ndcg_at_10: float
    ineligible_sources: int
    invalid_citations: int
    unjudged_sources: int
    dataset_complete: bool
    quality_gate_passed: bool


def evaluate_retrieval(
    queries: tuple[EvaluationQuery, ...], results: tuple[QueryResult, ...]
) -> RetrievalEvaluation:
    """Eligibility/citation checks must come from a real validated result export.

    Recall is fraction of known relevant sources, while hit rate matches the plan's
    'a known relevant source appears' criterion. Both are reported, not conflated.
    nDCG uses exponential graded gain. Duplicate excerpts never count as independent sources.
    """
    if not queries or len({q.id for q in queries}) != len(queries):
        raise ValueError("Supply nonempty, uniquely identified evaluation queries.")
    by_query = {r.query_id: r for r in results}
    if len(by_query) != len(results) or set(by_query) != {q.id for q in queries}:
        raise ValueError("Exactly one result, including empty results, is required per query.")
    recalls: list[float] = []
    bilingual: list[float] = []
    hits: list[float] = []
    ndcg: list[float] = []
    ineligible = invalid = unjudged = returned = 0
    for query in queries:
        grades = {j.source_id: j.relevance for j in query.judgments}
        relevant = {key for key, grade in grades.items() if grade > 0}
        sources: list[str] = []
        seen: set[str] = set()
        for item in by_query[query.id].sources:
            returned += 1
            ineligible += not item.eligible
            invalid += not item.citation_valid
            if item.source_id not in seen:
                sources.append(item.source_id)
                seen.add(item.source_id)
                unjudged += item.source_id not in grades
        found = relevant.intersection(sources[:20])
        recall = len(found) / len(relevant)
        recalls.append(recall)
        hits.append(float(bool(found)))
        if query.cross_language:
            bilingual.append(recall)
        dcg = sum((2 ** grades.get(key, 0) - 1) / log2(i + 2) for i, key in enumerate(sources[:10]))
        ideal = sum(
            (2**grade - 1) / log2(i + 2)
            for i, grade in enumerate(sorted(grades.values(), reverse=True)[:10])
        )
        ndcg.append(dcg / ideal)
    overall = sum(recalls) / len(recalls)
    cross = sum(bilingual) / len(bilingual) if bilingual else 0.0
    ranking = sum(ndcg) / len(ndcg)
    complete = len(queries) >= 200 and len(bilingual) >= 50 and unjudged == 0
    passed = (
        complete
        and returned > 0
        and overall >= 0.90
        and cross >= 0.85
        and ranking >= 0.80
        and ineligible == 0
        and invalid == 0
    )
    return RetrievalEvaluation(
        len(queries),
        len(bilingual),
        overall,
        cross,
        sum(hits) / len(hits),
        ranking,
        ineligible,
        invalid,
        unjudged,
        complete,
        passed,
    )
