"""Immutable human-answer evidence must reference this analysis round."""

from dataclasses import replace

import pytest

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.analysis.domain.errors import InvalidAnalysisContentError
from smb_requirement_agent.analysis.domain.value_objects import (
    AnalysisClarificationEvidence,
    ClarificationKind,
    HumanClarification,
    KnownFact,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@pytest.mark.parametrize("numbers", [(), (0,), (-1,), (1, 1), (True,)])
def test_human_evidence_numbers_must_be_nonempty_positive_and_unique(
    numbers: tuple[int, ...],
) -> None:
    with pytest.raises(InvalidAnalysisContentError):
        AnalysisClarificationEvidence("known_fact:one user", numbers)


def test_round_rejects_unknown_answers_and_duplicate_evidence_keys() -> None:
    evidence = AnalysisClarificationEvidence("known_fact:one user", (1,))
    analysis = RequirementAnalysis(
        RequirementId("req-1"),
        (KnownFact("One user"),),
        (),
        (),
        (),
        (),
        (),
        (),
        clarifications=(
            HumanClarification(ClarificationKind.OPEN_QUESTION, "How many?", "One user"),
        ),
        clarification_evidence=(evidence,),
    )
    with pytest.raises(InvalidAnalysisContentError):
        replace(analysis, clarification_evidence=(replace(evidence, clarification_numbers=(2,)),))
    with pytest.raises(InvalidAnalysisContentError):
        replace(analysis, clarification_evidence=(evidence, evidence))
