"""How well a prior-art judge tells delivered capabilities from shared topics (ADR-0102).

Each case is a proposed requirement, the historic candidates it would be shown, and which
of them a reviewer judged similar. Topic-only near misses are included on purpose: a judge
that matches on shared words alone fails the precision gate. Synthetic cases exercise the
harness; only human-reviewed cases are release evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.knowledge.application.ports.prior_art import (
    PriorArtCandidateInput,
    PriorArtJudgePort,
)

# What a judge must reach before an operator turns prior art on.
PRECISION_GATE = 0.8
RECALL_GATE = 0.7


@dataclass(frozen=True)
class PriorArtCase:
    case_id: str
    reviewer: str
    title: str
    subject: str
    candidates: tuple[PriorArtCandidateInput, ...]
    # Candidate numbers the reviewer judged similar; the rest are near misses.
    similar: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.reviewer.strip():
            raise ValueError("A case needs its identity and who judged it.")
        numbers = {candidate.number for candidate in self.candidates}
        if not set(self.similar) <= numbers:
            raise ValueError("A case can only judge candidates it shows.")


@dataclass(frozen=True)
class PriorArtEvaluation:
    cases: int
    pairs: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    invalid_citations: int
    quality_gate_passed: bool


def evaluate_prior_art(
    cases: tuple[PriorArtCase, ...], judge: PriorArtJudgePort
) -> PriorArtEvaluation:
    if not cases or len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Supply nonempty, uniquely identified cases.")
    tp = fp = fn = invalid = pairs = 0
    for case in cases:
        judgements = judge.judge(case.title, case.subject, case.candidates)
        by_number = {candidate.number: candidate for candidate in case.candidates}
        chosen: set[int] = set()
        for judgement in judgements:
            candidate = by_number.get(judgement.candidate_number)
            own = {item.number for item in candidate.evidence} if candidate else set()
            if candidate is None or not set(judgement.cited_evidence_numbers) <= own:
                invalid += 1
                continue
            chosen.add(judgement.candidate_number)
        expected = set(case.similar)
        pairs += len(case.candidates)
        tp += len(chosen & expected)
        fp += len(chosen - expected)
        fn += len(expected - chosen)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return PriorArtEvaluation(
        len(cases),
        pairs,
        tp,
        fp,
        fn,
        round(precision, 3),
        round(recall, 3),
        invalid,
        precision >= PRECISION_GATE and recall >= RECALL_GATE and invalid == 0,
    )
