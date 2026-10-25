"""When consolidation cannot shrink, validated findings are merged instead (ADR-0029)."""

from __future__ import annotations

import logging
from copy import deepcopy

import pytest
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    ActiveQuestionContext,
    AnalysisDocumentContext,
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.analysis.application.use_cases.analysis_mapping import (
    analysis_evidence_key,
)
from smb_requirement_agent.analysis.application.use_cases.evidence_analysis import (
    AnalyzeEvidencePacket,
    ConsolidateEvidenceAnalysis,
    PlanEvidencePackets,
    ValidateAnalysisCitations,
    _merged_fallback,
)
from smb_requirement_agent.analysis.domain.value_objects import (
    ClarificationKind,
    ClarificationSource,
    QuestionChangeAction,
)
from smb_requirement_agent.analysis.infrastructure.in_memory_evidence_fragment_cache import (
    InMemoryEvidenceFragmentCache,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.unit.analysis.test_structured_evidence_analysis import (
    NOW,
    RecordingEvidenceAnalyzer,
    _document,
)

REQUIREMENT = Requirement(
    RequirementId("requirement-1"),
    RequirementTitle("Bundle"),
    RequirementDescription("Analyze the BRD"),
    RequirementStatus.DRAFT,
)


def _section(index: int) -> AnalysisDocumentContext:
    document = _document()
    document["evidence_blocks"] = [document["evidence_blocks"][index]]
    return document


def _fragments() -> tuple[list[RequirementAnalysisCandidate], tuple[AnalysisDocumentContext, ...]]:
    sections = (_section(0), _section(1))
    provider = RecordingEvidenceAnalyzer()
    return [provider.analyze_evidence(REQUIREMENT, (), (item,), (), ()) for item in sections], (
        _document(),
    )


def test_consolidation_that_cannot_shrink_keeps_the_validated_findings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fragments, documents = _fragments()
    provider = RecordingEvidenceAnalyzer()
    # Room for one consolidation block per packet, so two findings stay two packets.
    planner = PlanEvidencePackets(12_200)
    consolidator = ConsolidateEvidenceAnalysis(
        planner,
        AnalyzeEvidencePacket(
            provider, ValidateAnalysisCitations(), InMemoryEvidenceFragmentCache(), FixedClock(NOW)
        ),
    )

    with caplog.at_level(logging.WARNING):
        result, provenance, _ = consolidator.execute(REQUIREMENT, (), fragments, (), ())

    assert provider.calls == 2
    assert len(provenance) == 2
    assert len(result["known_facts"]) == 2
    cited = sorted(
        reference["block_id"]
        for references in result["evidence_references"].values()
        for reference in references
    )
    assert cited == ["block-1", "block-2"]
    ValidateAnalysisCitations().execute(result, documents)
    assert "could not finish (no smaller round)" in caplog.text


def _question(question_id: str, subject: str, source: ClarificationSource) -> ActiveQuestionContext:
    return ActiveQuestionContext(
        question_id=question_id,
        kind=ClarificationKind.OPEN_QUESTION,
        subject=subject,
        rationale="Still undecided.",
        source=source,
    )


def test_fallback_retains_active_questions_and_drops_human_duplicates() -> None:
    fragments, documents = _fragments()
    found = "Which plans need consent?"
    human = "Who signs for a business line?"
    first = deepcopy(fragments[0])
    reference = next(iter(first["evidence_references"].values()))
    for subject in (found, human):
        first["open_questions"].append({"question": subject, "rationale": "Open in the BRD."})
        first["evidence_references"][analysis_evidence_key("open_question", subject)] = list(
            reference
        )
    carried = "Is consent recorded per line?"
    active = (
        _question("ai-found", found, ClarificationSource.AI),
        _question("ai-carried", carried, ClarificationSource.AI),
        _question("human", human, ClarificationSource.HUMAN),
    )

    result = _merged_fallback([first, fragments[1]], active, "no smaller round")

    assert [item["question"] for item in result["open_questions"]] == [found, carried]
    assert result["carried_questions"] == [analysis_evidence_key("open_question", carried)]
    assert [(item["question_id"], item["action"]) for item in result["question_reviews"]] == [
        ("ai-found", QuestionChangeAction.RETAINED),
        ("ai-carried", QuestionChangeAction.RETAINED),
    ]
    assert result["new_uncertainties"] == []
    assert analysis_evidence_key("open_question", human) not in result["evidence_references"]
    ValidateAnalysisCitations().execute(result, documents)
