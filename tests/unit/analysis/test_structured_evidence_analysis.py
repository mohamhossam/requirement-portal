"""Packet budgeting, citation validation, provenance, and fragment caching."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

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
    AssembleRequirementEvidence,
    ConsolidateEvidenceAnalysis,
    PlanEvidencePackets,
    StructuredRequirementAnalyzer,
    ValidateAnalysisCitations,
)
from smb_requirement_agent.analysis.application.use_cases.generation_effects import (
    accepted_generation_effects,
)
from smb_requirement_agent.analysis.domain.value_objects import (
    ClarificationKind,
    HumanClarification,
    IntentProposal,
)
from smb_requirement_agent.analysis.infrastructure.in_memory_evidence_fragment_cache import (
    InMemoryEvidenceFragmentCache,
)
from smb_requirement_agent.application.errors import RequirementAnalysisGenerationError
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

NOW = datetime(2026, 9, 7, tzinfo=UTC)


class RecordingEvidenceAnalyzer:
    model = "recording-vision"
    prompt_version = "evidence-v1"

    def __init__(self) -> None:
        self.calls = 0

    def analyze_evidence(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext],
        intent_decisions: Sequence[IntentProposal],
        active_questions: Sequence[ActiveQuestionContext],
    ) -> RequirementAnalysisCandidate:
        del requirement, clarifications, intent_decisions, active_questions
        self.calls += 1
        document = documents[0]
        block = document["evidence_blocks"][0]
        statement = f"Supported by {block['block_id']}"
        return RequirementAnalysisCandidate(
            known_facts=[statement],
            constraints=[],
            business_rules=[],
            assumptions=[],
            open_questions=[],
            ambiguities=[],
            potential_dependencies=[],
            intent_proposals=[],
            model=self.model,
            prompt_version=self.prompt_version,
            evidence_references={
                analysis_evidence_key("known_fact", statement): [
                    {
                        "document_id": document["document_id"],
                        "version_id": document["version_id"],
                        "checksum_sha256": document["checksum_sha256"],
                        "block_id": block["block_id"],
                        "label": block["label"],
                    }
                ]
            },
        )


class FailOnceOnSecondEvidenceAnalyzer(RecordingEvidenceAnalyzer):
    def analyze_evidence(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext],
        intent_decisions: Sequence[IntentProposal],
        active_questions: Sequence[ActiveQuestionContext],
    ) -> RequirementAnalysisCandidate:
        if self.calls == 1:
            self.calls += 1
            raise RequirementAnalysisGenerationError("Second packet failed.")
        return super().analyze_evidence(
            requirement,
            clarifications,
            documents,
            intent_decisions,
            active_questions,
        )


def test_consolidation_restores_human_support_without_document_identity() -> None:
    provider = RecordingEvidenceAnalyzer()
    validator = ValidateAnalysisCitations()
    packet_analyzer = AnalyzeEvidencePacket(
        provider, validator, InMemoryEvidenceFragmentCache(), FixedClock(NOW)
    )
    consolidator = ConsolidateEvidenceAnalysis(PlanEvidencePackets(100_000), packet_analyzer)
    clarification = HumanClarification(
        ClarificationKind.OPEN_QUESTION, "How do plans differ?", "DEL serves a single user."
    )
    candidate = RequirementAnalysisCandidate(
        known_facts=[clarification.answer],
        constraints=[],
        business_rules=[],
        assumptions=[],
        open_questions=[],
        ambiguities=[],
        potential_dependencies=[],
        intent_proposals=[],
        model="test-model",
        prompt_version="test-prompt",
        evidence_references={analysis_evidence_key("known_fact", clarification.answer): []},
        clarification_references={analysis_evidence_key("known_fact", clarification.answer): [1]},
    )
    requirement = Requirement(
        RequirementId("req-1"),
        RequirementTitle("Plans"),
        RequirementDescription("Compare plans"),
        RequirementStatus.DRAFT,
    )
    result, _, _ = consolidator.execute(requirement, (clarification,), (candidate,), (), ())
    validator.execute(result, (), (clarification,))
    key = analysis_evidence_key("known_fact", result["known_facts"][0])
    assert result["evidence_references"][key] == []
    assert result["clarification_references"][key] == [1]


@pytest.mark.parametrize("numbers", [[0], [2], [1, 1], [True]])
def test_human_citations_require_unique_existing_answer_numbers(numbers: list[int]) -> None:
    clarification = HumanClarification(ClarificationKind.OPEN_QUESTION, "How?", "One user.")
    candidate = RequirementAnalysisCandidate(
        known_facts=[clarification.answer],
        constraints=[],
        business_rules=[],
        assumptions=[],
        open_questions=[],
        ambiguities=[],
        potential_dependencies=[],
        intent_proposals=[],
        model="test-model",
        prompt_version="test-prompt",
        clarification_references={
            analysis_evidence_key("known_fact", clarification.answer): numbers
        },
    )
    with pytest.raises(RequirementAnalysisGenerationError, match="invalid human answer"):
        ValidateAnalysisCitations().execute(candidate, (), (clarification,))


class NoOpFallback:
    def analyze(self, *args: object, **kwargs: object) -> RequirementAnalysisCandidate:
        raise AssertionError("Structured evidence must not use the legacy analyzer path.")


class RecordingProgress:
    def __init__(self) -> None:
        self.phases: list[str] = []

    def report(self, requirement_id: RequirementId, phase: str, *args: object) -> None:
        del requirement_id, args
        self.phases.append(phase)


def _document(checksum: str = "a" * 64) -> AnalysisDocumentContext:
    return AnalysisDocumentContext(
        document_id="document-1",
        version_id="version-1",
        filename="source.docx",
        checksum_sha256=checksum,
        extracted_text="Alpha\nBeta",
        extraction_version="structured-evidence-v1",
        evidence_blocks=[
            {
                "block_id": "block-1",
                "kind": "paragraph",
                "section_path": ["BUC1"],
                "label": "Description",
                "text": "Alpha" * 50,
                "asset_id": None,
            },
            {
                "block_id": "block-2",
                "kind": "table_row",
                "section_path": ["BUC2"],
                "label": "Table 1, row 2",
                "text": "Beta" * 50,
                "asset_id": None,
            },
        ],
        image_assets=[],
    )


def test_packetized_analysis_caches_fragments_and_records_stages() -> None:
    provider = RecordingEvidenceAnalyzer()
    validator = ValidateAnalysisCitations()
    progress = RecordingProgress()
    planner = PlanEvidencePackets(12_400)
    packet_analyzer = AnalyzeEvidencePacket(
        provider,
        validator,
        InMemoryEvidenceFragmentCache(),
        FixedClock(NOW),
    )
    analyzer = StructuredRequirementAnalyzer(
        NoOpFallback(),
        AssembleRequirementEvidence(),
        planner,
        packet_analyzer,
        ConsolidateEvidenceAnalysis(planner, packet_analyzer),
        validator,
        FixedClock(NOW),
        progress,
    )
    requirement = Requirement(
        RequirementId("requirement-1"),
        RequirementTitle("Bundle"),
        RequirementDescription("Analyze the BRD"),
        RequirementStatus.DRAFT,
    )

    first = _accepted_analyze(analyzer, requirement, (), (_document(),))
    calls_after_first = provider.calls
    second = _accepted_analyze(analyzer, requirement, (), (_document(),))

    assert provider.calls == calls_after_first
    assert len(first["stage_provenance"]) == 3
    assert first["known_facts"] == second["known_facts"]
    assert "validating_evidence_references" in progress.phases


def test_failed_multi_packet_analysis_does_not_commit_partial_fragment_cache() -> None:
    provider = FailOnceOnSecondEvidenceAnalyzer()
    validator = ValidateAnalysisCitations()
    planner = PlanEvidencePackets(12_400)
    packet_analyzer = AnalyzeEvidencePacket(
        provider,
        validator,
        InMemoryEvidenceFragmentCache(),
        FixedClock(NOW),
    )
    analyzer = StructuredRequirementAnalyzer(
        NoOpFallback(),
        AssembleRequirementEvidence(),
        planner,
        packet_analyzer,
        ConsolidateEvidenceAnalysis(planner, packet_analyzer),
        validator,
        FixedClock(NOW),
        RecordingProgress(),
    )
    requirement = Requirement(
        RequirementId("requirement-1"),
        RequirementTitle("Bundle"),
        RequirementDescription("Analyze the BRD"),
        RequirementStatus.DRAFT,
    )

    with pytest.raises(RequirementAnalysisGenerationError, match="Second packet failed"):
        _accepted_analyze(analyzer, requirement, (), (_document(),))

    _accepted_analyze(analyzer, requirement, (), (_document(),))

    assert provider.calls == 5


def test_packet_cache_misses_when_extraction_version_changes() -> None:
    provider = RecordingEvidenceAnalyzer()
    validator = ValidateAnalysisCitations()
    packet = AnalyzeEvidencePacket(
        provider, validator, InMemoryEvidenceFragmentCache(), FixedClock(NOW)
    )
    requirement = Requirement(
        RequirementId("requirement-1"),
        RequirementTitle("Bundle"),
        RequirementDescription("Analyze"),
        RequirementStatus.DRAFT,
    )
    first = _document()
    second = _document()
    second["extraction_version"] = "structured-evidence-v2"

    packet.execute(requirement, (), (first,), ())
    packet.execute(requirement, (), (second,), ())

    assert provider.calls == 2


def test_packet_cache_misses_when_document_identity_changes() -> None:
    provider = RecordingEvidenceAnalyzer()
    validator = ValidateAnalysisCitations()
    packet = AnalyzeEvidencePacket(
        provider, validator, InMemoryEvidenceFragmentCache(), FixedClock(NOW)
    )
    requirement = Requirement(
        RequirementId("requirement-1"),
        RequirementTitle("Bundle"),
        RequirementDescription("Analyze"),
        RequirementStatus.DRAFT,
    )
    _, _, pending = packet.execute(requirement, (), (_document(),), ())
    assert pending is not None
    packet.commit((pending,))
    replacement = _document()
    replacement["document_id"] = "document-2"
    replacement["version_id"] = "version-2"

    candidate, _, _ = packet.execute(requirement, (), (replacement,), ())

    reference = next(iter(candidate["evidence_references"].values()))[0]
    assert provider.calls == 2
    assert reference["document_id"] == "document-2"
    assert reference["version_id"] == "version-2"


def test_citation_validator_rejects_unknown_and_missing_citations() -> None:
    candidate = RecordingEvidenceAnalyzer().analyze_evidence(
        Requirement(
            RequirementId("requirement-1"),
            RequirementTitle("Bundle"),
            RequirementDescription("Analyze"),
            RequirementStatus.DRAFT,
        ),
        (),
        (_document(),),
        (),
        (),
    )
    key = next(iter(candidate["evidence_references"]))
    candidate["evidence_references"][key][0]["block_id"] = "unknown"

    with pytest.raises(RequirementAnalysisGenerationError, match="out-of-packet"):
        ValidateAnalysisCitations().execute(candidate, (_document(),))

    candidate["evidence_references"] = {}
    with pytest.raises(RequirementAnalysisGenerationError, match="cite every"):
        ValidateAnalysisCitations().execute(candidate, (_document(),))


def test_citation_validator_rejects_blank_mixed_and_stale_citations() -> None:
    document = _document()
    candidate = RecordingEvidenceAnalyzer().analyze_evidence(
        Requirement(
            RequirementId("requirement-1"),
            RequirementTitle("Bundle"),
            RequirementDescription("Analyze"),
            RequirementStatus.DRAFT,
        ),
        (),
        (document,),
        (),
        (),
    )
    key = next(iter(candidate["evidence_references"]))
    reference = candidate["evidence_references"][key][0]
    reference["block_id"] = ""
    with pytest.raises(RequirementAnalysisGenerationError, match="blank, stale"):
        ValidateAnalysisCitations().execute(candidate, (document,))

    reference["block_id"] = "block-1"
    candidate["evidence_references"][key].append({**reference, "block_id": "outside-packet"})
    with pytest.raises(RequirementAnalysisGenerationError, match="out-of-packet"):
        ValidateAnalysisCitations().execute(candidate, (document,))

    candidate["evidence_references"][key] = [{**reference, "checksum_sha256": "b" * 64}]
    with pytest.raises(RequirementAnalysisGenerationError, match="stale"):
        ValidateAnalysisCitations().execute(candidate, (document,))


def test_planner_splits_oversized_text_without_changing_source_block_id() -> None:
    document = _document()
    document["evidence_blocks"] = [{**document["evidence_blocks"][0], "text": "x" * 1_000}]

    packets = PlanEvidencePackets(12_400).execute((document,))

    assert len(packets) > 1
    assert {block["block_id"] for packet in packets for block in packet[0]["evidence_blocks"]} == {
        "block-1"
    }


def test_planner_keeps_business_use_cases_as_traceable_section_packets() -> None:
    document = _document()
    document["evidence_blocks"] = [
        {
            "block_id": "overview",
            "kind": "paragraph",
            "section_path": ["Business Requirement"],
            "label": "Objective",
            "text": "One initiative",
            "asset_id": None,
        },
        {
            "block_id": "buc-1",
            "kind": "heading",
            "section_path": ["[BUC1]: Activation"],
            "label": "[BUC1]: Activation",
            "text": "[BUC1]: Activation",
            "asset_id": None,
        },
        {
            "block_id": "buc-1-flow",
            "kind": "table_row",
            "section_path": ["[BUC1]: Activation"],
            "label": "Basic flow",
            "text": "Activate the service",
            "asset_id": None,
        },
        {
            "block_id": "buc-2",
            "kind": "heading",
            "section_path": ["[BUC2]: Cessation"],
            "label": "[BUC2]: Cessation",
            "text": "[BUC2]: Cessation",
            "asset_id": None,
        },
    ]

    packets = PlanEvidencePackets(60_000).execute((document,))

    assert [
        [block["block_id"] for block in packet[0]["evidence_blocks"]] for packet in packets
    ] == [
        ["overview"],
        ["buc-1", "buc-1-flow"],
        ["buc-2"],
    ]


def test_consolidation_preserves_exact_references_across_multiple_documents() -> None:
    provider = RecordingEvidenceAnalyzer()
    planner = PlanEvidencePackets(13_000)
    validator = ValidateAnalysisCitations()
    packet_analyzer = AnalyzeEvidencePacket(
        provider, validator, InMemoryEvidenceFragmentCache(), FixedClock(NOW)
    )
    analyzer = StructuredRequirementAnalyzer(
        NoOpFallback(),
        AssembleRequirementEvidence(),
        planner,
        packet_analyzer,
        ConsolidateEvidenceAnalysis(planner, packet_analyzer),
        validator,
        FixedClock(NOW),
        RecordingProgress(),
    )
    second = _document("b" * 64)
    second["document_id"] = "document-2"
    second["version_id"] = "version-2"
    requirement = Requirement(
        RequirementId("requirement-1"),
        RequirementTitle("Bundle"),
        RequirementDescription("Analyze"),
        RequirementStatus.DRAFT,
    )

    result = _accepted_analyze(analyzer, requirement, (), (_document(), second))

    reference = next(iter(result["evidence_references"].values()))[0]
    assert reference["document_id"] in {"document-1", "document-2"}
    assert reference["document_id"] != "evidence-consolidation"


def _accepted_analyze(
    analyzer: StructuredRequirementAnalyzer, *args: Any
) -> RequirementAnalysisCandidate:
    with accepted_generation_effects():
        return analyzer.analyze(*args)


def test_packet_cache_includes_requirement_and_clarification_semantics() -> None:
    from dataclasses import replace

    from smb_requirement_agent.analysis.domain.value_objects import ClarificationKind

    provider = RecordingEvidenceAnalyzer()
    packet = AnalyzeEvidencePacket(
        provider, ValidateAnalysisCitations(), InMemoryEvidenceFragmentCache(), FixedClock(NOW)
    )
    requirement = Requirement(
        RequirementId("semantic-input"),
        RequirementTitle("Bundle"),
        RequirementDescription("Analyze the BRD"),
        RequirementStatus.DRAFT,
    )
    _, _, pending = packet.execute(requirement, (), (_document(),), ())
    assert pending is not None
    packet.commit((pending,))
    packet.execute(requirement, (), (_document(),), ())
    assert provider.calls == 1
    packet.execute(
        replace(requirement, title=RequirementTitle("Changed scope")), (), (_document(),), ()
    )
    packet.execute(
        requirement,
        (HumanClarification(ClarificationKind.OPEN_QUESTION, "Channel", "Web"),),
        (_document(),),
        (),
    )
    assert provider.calls == 3


def test_packet_cache_is_scoped_to_configuration_fingerprint() -> None:
    class ConfiguredAnalyzer(RecordingEvidenceAnalyzer):
        configuration_fingerprint = "configuration-one"

    provider = ConfiguredAnalyzer()
    packet = AnalyzeEvidencePacket(
        provider, ValidateAnalysisCitations(), InMemoryEvidenceFragmentCache(), FixedClock(NOW)
    )
    requirement = Requirement(
        RequirementId("cache-profile"),
        RequirementTitle("Bundle"),
        RequirementDescription("Analyze"),
        RequirementStatus.DRAFT,
    )
    _, _, pending = packet.execute(requirement, (), (_document(),), ())
    assert pending is not None
    packet.commit((pending,))
    packet.execute(requirement, (), (_document(),), ())
    assert provider.calls == 1
    provider.configuration_fingerprint = "configuration-two"
    packet.execute(requirement, (), (_document(),), ())
    assert provider.calls == 2
