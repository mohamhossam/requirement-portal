"""Contract tests for the local OpenAI-compatible LLM adapters."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest
from smb_kernel.llm.local_structured_output import (
    LocalLLMError,
    LocalStructuredOutputClient,
)
from smb_kernel.llm.structured_output import truncated

from smb_requirement_agent.analysis.application.errors import RequirementAnalysisGenerationError
from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    ActiveQuestionContext,
    AnalysisDocumentContext,
    AnalysisEvidenceBlock,
)
from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.analysis.domain.value_objects import (
    Assumption,
    ClarificationKind,
    ClarificationSource,
    HumanClarification,
    KnownFact,
    OpenQuestion,
)
from smb_requirement_agent.analysis.infrastructure.llm.analysis_mappers import to_analysis_candidate
from smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer import (
    LocalRequirementAnalyzer,
)
from smb_requirement_agent.analysis.infrastructure.llm.schemas.analysis_schema import (
    ActiveQuestionReviewSchema,
    AnalysisEvidenceCitationSchema,
    ClarificationReviewSchema,
    DesiredOutcomeReviewSchema,
    IndexedActiveQuestionReviewSchema,
    IndexedAnalysisEvidenceDecisionSchema,
    IndexedAnalysisEvidenceRecoverySchema,
    IndexedQuestionReconciliationSchema,
    IndexedUncertaintyRationaleRecoverySchema,
    IndexedUncertaintyRationaleSchema,
    OpenQuestionSchema,
    RequirementAnalysisSchema,
    UncertaintySchema,
)
from smb_requirement_agent.breakdown.application.errors import (
    EpicGenerationError,
    FeatureGenerationError,
)
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.breakdown.domain.epic.value_objects import (
    BusinessCase,
    BusinessOutcome,
    EpicId,
    EpicName,
    EpicStatus,
)
from smb_requirement_agent.breakdown.infrastructure.llm.local_epic_generator import (
    LocalEpicGenerator,
)
from smb_requirement_agent.breakdown.infrastructure.llm.local_feature_generator import (
    LocalFeatureGenerator,
)
from smb_requirement_agent.breakdown.infrastructure.llm.schemas.epic_schema import EpicSchema
from smb_requirement_agent.breakdown.infrastructure.llm.schemas.feature_schema import (
    FeatureItemSchema,
    FeatureSetSchema,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementContext,
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@pytest.fixture
def requirement() -> Requirement:
    return Requirement(
        id=RequirementId("req-1"),
        title=RequirementTitle("Bundle ordering"),
        description=RequirementDescription("Order bundles in the portal"),
        status=RequirementStatus.DRAFT,
        desired_outcome=RequirementContext("Customers can order bundles in the portal."),
    )


@pytest.fixture
def analysis() -> RequirementAnalysis:
    return RequirementAnalysis(
        requirement_id=RequirementId("req-1"),
        known_facts=(KnownFact("Bundles exist"),),
        constraints=(),
        business_rules=(),
        assumptions=(Assumption("Billing supports bundles"),),
        open_questions=(OpenQuestion("Which products?", "Scope is unclear"),),
        ambiguities=(),
        potential_dependencies=(),
    )


@pytest.fixture
def epic() -> Epic:
    return Epic(
        id=EpicId("epic-1"),
        requirement_id=RequirementId("req-1"),
        name=EpicName("SMB Bundle Offer"),
        outcome=BusinessOutcome("Bundles can be ordered"),
        business_case=BusinessCase("Supports the stated offer"),
        status=EpicStatus.APPROVED,
        provenance=Provenance(
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
            model="local-model",
            prompt_version="epic-v1",
        ),
    )


def _response(payload: object) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    return response


def _structured_document(*, with_image: bool = False) -> AnalysisDocumentContext:
    block = AnalysisEvidenceBlock(
        block_id="block-1",
        kind="image" if with_image else "paragraph",
        section_path=["Scope"],
        label="Bundle rule",
        text=None if with_image else "Bundles are ordered in the portal.",
        asset_id="asset-1" if with_image else None,
    )
    document = AnalysisDocumentContext(
        document_id="document-1",
        version_id="version-1",
        filename="source.docx",
        checksum_sha256="a" * 64,
        extracted_text=block["text"] or "[image]",
        evidence_blocks=[block],
    )
    if with_image:
        document["image_assets"] = [
            {
                "asset_id": "asset-1",
                "block_id": "block-1",
                "mime_type": "image/png",
                "content": b"safe-image-bytes",
            }
        ]
    return document


def test_local_client_sends_json_schema_and_parses_content() -> None:
    parsed_json = json.dumps(
        {
            "name": "SMB Bundle Offer",
            "outcome": "Bundles can be ordered",
            "business_case": "Supports the stated offer",
        }
    )
    with patch(
        "smb_kernel.llm.local_structured_output.httpx.Client.post",
        return_value=_response({"choices": [{"message": {"content": parsed_json}}]}),
    ) as post:
        client = LocalStructuredOutputClient(
            base_url="http://127.0.0.1:1234/v1/",
            http_client=httpx.Client(),
            model="local-model",
            timeout_seconds=90,
            reasoning_effort=None,
        )
        result = client.parse(
            system_prompt="system",
            user_prompt="user",
            schema_type=EpicSchema,
        )

    assert result.name == "SMB Bundle Offer"
    call = post.call_args
    assert call.args[0] == "http://127.0.0.1:1234/v1/chat/completions"
    assert call.kwargs["timeout"] == 90
    assert call.kwargs["json"]["model"] == "local-model"
    assert call.kwargs["json"]["response_format"]["json_schema"]["schema"]["title"] == (
        "EpicSchema"
    )
    assert call.kwargs["json"]["max_tokens"] == 4096
    assert "reasoning_effort" not in call.kwargs["json"]


def test_local_client_disables_reasoning_and_accepts_ollama_reasoning_fallback() -> None:
    parsed_json = json.dumps(
        {
            "name": "SMB Bundle Offer",
            "outcome": "Bundles can be ordered",
            "business_case": "Supports the stated offer",
        }
    )
    with patch(
        "smb_kernel.llm.local_structured_output.httpx.Client.post",
        return_value=_response(
            {"choices": [{"message": {"content": "", "reasoning": parsed_json}}]}
        ),
    ) as post:
        client = LocalStructuredOutputClient(
            base_url="http://127.0.0.1:11434/v1",
            http_client=httpx.Client(),
            model="qwen3-vl:8b",
            timeout_seconds=90,
            reasoning_effort="none",
        )
        result = client.parse(
            system_prompt="system",
            user_prompt="user",
            schema_type=EpicSchema,
        )

    assert result.name == "SMB Bundle Offer"
    assert post.call_args.kwargs["json"]["reasoning_effort"] == "none"


def test_local_client_reports_output_token_truncation_explicitly() -> None:
    with patch(
        "smb_kernel.llm.local_structured_output.httpx.Client.post",
        return_value=_response(
            {
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": '{"known_facts":["unfinished'},
                    }
                ]
            }
        ),
    ):
        client = LocalStructuredOutputClient(
            base_url="http://127.0.0.1:11434/v1",
            http_client=httpx.Client(),
            model="qwen3-vl:8b",
            timeout_seconds=90,
            reasoning_effort="none",
        )

        with pytest.raises(LocalLLMError, match="output was truncated") as raised:
            client.parse(
                system_prompt="system",
                user_prompt="user",
                schema_type=RequirementAnalysisSchema,
            )
    # A reader that can ask for less tells a cut-off answer apart (ADR-0091).
    assert truncated(raised.value)


def test_local_client_rejects_oversized_context_without_dropping_human_input() -> None:
    client = LocalStructuredOutputClient(
        base_url="http://127.0.0.1:11434/v1",
        http_client=httpx.Client(),
        model="qwen3-vl:8b",
        timeout_seconds=90,
        reasoning_effort="none",
        context_window_tokens=1024,
        max_output_tokens=256,
    )

    with pytest.raises(LocalLLMError, match="Human clarifications were not discarded"):
        client.parse(
            system_prompt="system",
            user_prompt="human decision " * 300,
            schema_type=EpicSchema,
        )


def test_analysis_mapper_accepts_at_most_twelve_reconciled_uncertainties() -> None:
    candidate = to_analysis_candidate(
        RequirementAnalysisSchema(
            known_facts=["A fact"],
            new_uncertainties=[
                *(
                    UncertaintySchema(
                        kind=ClarificationKind.OPEN_QUESTION,
                        subject=f"Question {index}",
                        rationale="Needed",
                    )
                    for index in range(8)
                ),
                *(
                    UncertaintySchema(
                        kind=ClarificationKind.ASSUMPTION,
                        subject=f"Assumption {index}",
                    )
                    for index in range(4)
                ),
            ],
        ),
        model="test-model",
        prompt_version="test-prompt",
    )

    assert len(candidate["open_questions"]) == 8
    assert len(candidate["assumptions"]) == 4
    assert candidate["potential_dependencies"] == []


def test_analysis_mapper_accepts_retain_replace_and_new_uncertainties() -> None:
    active = (
        ActiveQuestionContext(
            question_id="q-1",
            kind=ClarificationKind.OPEN_QUESTION,
            subject="Who owns fallout?",
            rationale="Ownership is unclear.",
            source=ClarificationSource.AI,
        ),
        ActiveQuestionContext(
            question_id="q-2",
            kind=ClarificationKind.ASSUMPTION,
            subject="Coverage data is current.",
            rationale=None,
            source=ClarificationSource.AI,
        ),
    )
    candidate = to_analysis_candidate(
        RequirementAnalysisSchema(
            known_facts=["A fact"],
            active_question_reviews=[
                ActiveQuestionReviewSchema(
                    question_id="q-1",
                    action="retain",
                    rationale="Ownership remains unclear.",
                ),
                ActiveQuestionReviewSchema(
                    question_id="q-2",
                    action="replace",
                    rationale="The same gap needs a testable question.",
                    replacement=UncertaintySchema(
                        kind=ClarificationKind.OPEN_QUESTION,
                        subject="How is coverage freshness verified?",
                        rationale="The validation method is missing.",
                    ),
                ),
            ],
            new_uncertainties=[
                UncertaintySchema(
                    kind=ClarificationKind.POTENTIAL_DEPENDENCY,
                    subject="Coverage service availability",
                )
            ],
        ),
        model="test-model",
        prompt_version="analysis-v4",
        active_questions=active,
    )

    assert [item["action"] for item in candidate["question_reviews"]] == [
        "retained",
        "replaced",
    ]
    assert candidate["open_questions"] == [
        {"question": "Who owns fallout?", "rationale": "Ownership is unclear."},
        {
            "question": "How is coverage freshness verified?",
            "rationale": "The validation method is missing.",
        },
    ]
    assert candidate["potential_dependencies"] == ["Coverage service availability"]


@pytest.mark.parametrize(
    "reviews",
    [
        [],
        [
            ActiveQuestionReviewSchema(
                question_id="unknown",
                action="retain",
                rationale="Still needed.",
            )
        ],
        [
            ActiveQuestionReviewSchema(
                question_id="q-1",
                action="retain",
                rationale="Still needed.",
            ),
            ActiveQuestionReviewSchema(
                question_id="q-1",
                action="retire",
                rationale="No longer needed.",
            ),
        ],
        [
            ActiveQuestionReviewSchema(
                question_id="q-1",
                action="replace",
                rationale="Needs revision.",
            )
        ],
        [
            ActiveQuestionReviewSchema(
                question_id="q-1",
                action="retain",
                rationale="   ",
            )
        ],
        [
            ActiveQuestionReviewSchema(
                question_id="q-1",
                action="replace",
                rationale="Needs revision.",
                replacement=UncertaintySchema(
                    kind=ClarificationKind.OPEN_QUESTION,
                    subject="Who owns fallout?",
                    rationale="Same wording.",
                ),
            )
        ],
    ],
)
def test_analysis_mapper_rejects_incomplete_or_inconsistent_reviews(
    reviews: list[ActiveQuestionReviewSchema],
) -> None:
    active = (
        ActiveQuestionContext(
            question_id="q-1",
            kind=ClarificationKind.OPEN_QUESTION,
            subject="Who owns fallout?",
            rationale="Ownership is unclear.",
            source=ClarificationSource.AI,
        ),
    )

    with pytest.raises(RequirementAnalysisGenerationError):
        to_analysis_candidate(
            RequirementAnalysisSchema(known_facts=["A fact"], active_question_reviews=reviews),
            model="test-model",
            prompt_version="analysis-v4",
            active_questions=active,
        )


def test_analysis_mapper_rejects_reviews_or_duplicates_of_human_questions() -> None:
    human = ActiveQuestionContext(
        question_id="human-1",
        kind=ClarificationKind.OPEN_QUESTION,
        subject="Who approves launch?",
        rationale=None,
        source=ClarificationSource.HUMAN,
    )
    reviewed = RequirementAnalysisSchema(
        known_facts=["A fact"],
        active_question_reviews=[
            ActiveQuestionReviewSchema(
                question_id="human-1",
                action="retain",
                rationale="Still needed.",
            )
        ],
    )
    duplicated = RequirementAnalysisSchema(
        known_facts=["A fact"],
        new_uncertainties=[
            UncertaintySchema(
                kind=ClarificationKind.AMBIGUITY,
                subject="Who approves launch?",
                rationale="Approval is unclear.",
            )
        ],
    )

    with pytest.raises(RequirementAnalysisGenerationError, match="protected human"):
        to_analysis_candidate(
            reviewed,
            model="test-model",
            prompt_version="analysis-v4",
            active_questions=(human,),
        )
    with pytest.raises(RequirementAnalysisGenerationError, match="protected human"):
        to_analysis_candidate(
            duplicated,
            model="test-model",
            prompt_version="analysis-v4",
            active_questions=(human,),
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "no choices"),
        ({"choices": []}, "no choices"),
        ({"choices": [{}]}, "no assistant message"),
        ({"choices": [{"message": {"content": "  "}}]}, "empty completion"),
        ({"choices": [{"message": {"content": "not-json"}}]}, "did not match"),
    ],
)
def test_local_client_rejects_malformed_responses(payload: object, message: str) -> None:
    with patch(
        "smb_kernel.llm.local_structured_output.httpx.Client.post",
        return_value=_response(payload),
    ):
        client = LocalStructuredOutputClient(
            base_url="http://127.0.0.1:1234/v1",
            http_client=httpx.Client(),
            model="local-model",
            timeout_seconds=90,
            reasoning_effort=None,
        )
        with pytest.raises(LocalLLMError, match=message):
            client.parse(system_prompt="system", user_prompt="user", schema_type=EpicSchema)


def test_local_client_maps_connection_failures() -> None:
    with patch(
        "smb_kernel.llm.local_structured_output.httpx.Client.post",
        side_effect=httpx.ConnectError("server is offline"),
    ):
        client = LocalStructuredOutputClient(
            base_url="http://127.0.0.1:1234/v1",
            http_client=httpx.Client(),
            model="local-model",
            timeout_seconds=90,
            reasoning_effort=None,
        )
        with pytest.raises(LocalLLMError, match="server is offline"):
            client.parse(system_prompt="system", user_prompt="user", schema_type=EpicSchema)


def test_local_client_rejects_non_json_http_response() -> None:
    response = MagicMock()
    response.json.side_effect = ValueError("not json")
    with patch(
        "smb_kernel.llm.local_structured_output.httpx.Client.post",
        return_value=response,
    ):
        client = LocalStructuredOutputClient(
            base_url="http://127.0.0.1:1234/v1",
            http_client=httpx.Client(),
            model="local-model",
            timeout_seconds=90,
            reasoning_effort=None,
        )
        with pytest.raises(LocalLLMError, match="non-JSON"):
            client.parse(system_prompt="system", user_prompt="user", schema_type=EpicSchema)


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_analysis_cleans_schema_valid_blanks(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client_type.return_value.model = "local-model"
    client_type.return_value.parse.return_value = RequirementAnalysisSchema(
        known_facts=["", "  Supported fact  "],
        new_uncertainties=[
            UncertaintySchema(
                kind=ClarificationKind.OPEN_QUESTION,
                subject=" Real question ",
                rationale=" Rationale ",
            ),
        ],
    )

    result = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    ).analyze(requirement, ())

    assert result["known_facts"] == ["Supported fact"]
    assert result["open_questions"] == [{"question": "Real question", "rationale": "Rationale"}]
    assert result["model"] == "local-model"
    assert result["prompt_version"] == "analysis-v24-citation-business-context"


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_analysis_collapses_duplicate_uncertainty_without_retry(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.return_value = RequirementAnalysisSchema(
        known_facts=["Bundles are ordered in the portal."],
        new_uncertainties=[
            UncertaintySchema(
                kind=ClarificationKind.AMBIGUITY,
                subject=" Supported channel is unclear. ",
                rationale="The channel is not named.",
            ),
            UncertaintySchema(
                kind=ClarificationKind.AMBIGUITY,
                subject="supported channel is unclear.",
                rationale="The requirement does not identify which ordering channel is supported.",
            ),
        ],
    )

    result = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    ).analyze(requirement, ())

    assert result["ambiguities"] == [
        {
            "statement": "Supported channel is unclear.",
            "reason": "The requirement does not identify which ordering channel is supported.",
        }
    ]
    assert client.parse.call_count == 1


def test_analysis_mapper_rejects_duplicate_uncertainty_with_conflicting_kinds() -> None:
    parsed = RequirementAnalysisSchema(
        known_facts=["Bundles are ordered in the portal."],
        new_uncertainties=[
            UncertaintySchema(
                kind=ClarificationKind.AMBIGUITY,
                subject="Supported channel is unclear.",
                rationale="The channel is not named.",
            ),
            UncertaintySchema(
                kind=ClarificationKind.OPEN_QUESTION,
                subject="supported channel is unclear.",
                rationale="Which channel should support ordering?",
            ),
        ],
    )

    with pytest.raises(RequirementAnalysisGenerationError, match="conflicting classifications"):
        to_analysis_candidate(parsed, model="local-model", prompt_version="test-prompt")


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_analysis_discards_citations_when_no_evidence_was_supplied(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client_type.return_value.model = "local-model"
    client_type.return_value.parse.return_value = RequirementAnalysisSchema(
        known_facts=["Bundles are ordered in the portal."],
        evidence_citations=[
            AnalysisEvidenceCitationSchema(
                kind="known_fact",
                subject="Bundles are ordered in the portal.",
                block_ids=["invented-block"],
            )
        ],
    )
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    candidate = analyzer.analyze(requirement, ())

    assert candidate["known_facts"] == ["Bundles are ordered in the portal."]
    assert "evidence_references" not in candidate


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_analysis_keeps_valid_human_citations_and_drops_stale_ones(
    client_type: MagicMock, requirement: Requirement
) -> None:
    answer_fact = "The configured fraud policy applies to transfers."
    client_type.return_value.model = "local-model"
    client_type.return_value.parse.return_value = RequirementAnalysisSchema(
        known_facts=["Bundles are ordered in the portal.", answer_fact],
        evidence_citations=[
            AnalysisEvidenceCitationSchema(
                kind="known_fact",
                subject=answer_fact,
                block_ids=["invented-block"],
                clarification_numbers=[1],
            ),
            AnalysisEvidenceCitationSchema(
                kind="open_question",
                subject="Which fraud rules apply?",
                clarification_numbers=[1],
            ),
            AnalysisEvidenceCitationSchema(
                kind="known_fact",
                subject="Bundles are ordered in the portal.",
                clarification_numbers=[2],
            ),
        ],
    )
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    candidate = analyzer.analyze(
        requirement,
        (
            HumanClarification(
                ClarificationKind.OPEN_QUESTION,
                "Which fraud rules apply?",
                "Use the configured fraud policy.",
            ),
        ),
    )

    assert candidate["known_facts"] == ["Bundles are ordered in the portal.", answer_fact]
    assert candidate["clarification_references"] == {"known_fact:" + answer_fact.casefold(): [1]}
    assert candidate["evidence_references"] == {"known_fact:" + answer_fact.casefold(): []}


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_structured_analysis_requires_vision_and_passes_safe_images(
    client_type: MagicMock, requirement: Requirement
) -> None:
    document = {
        "document_id": "document-1",
        "version_id": "version-1",
        "filename": "source.docx",
        "checksum_sha256": "a" * 64,
        "extracted_text": "[image]",
        "evidence_blocks": [
            {
                "block_id": "image-block",
                "kind": "image",
                "section_path": ["BUC4"],
                "label": "Workflow screenshot",
                "text": None,
                "asset_id": "asset-1",
            }
        ],
        "image_assets": [
            {
                "asset_id": "asset-1",
                "block_id": "image-block",
                "mime_type": "image/png",
                "content": b"safe-image-bytes",
            }
        ],
    }
    disabled = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )
    with pytest.raises(RequirementAnalysisGenerationError, match="local vision is disabled"):
        disabled.analyze_evidence(requirement, (), (document,), (), ())  # type: ignore[arg-type]

    client = client_type.return_value
    client.model = "local-model"
    client.parse.return_value = RequirementAnalysisSchema(
        known_facts=["The screenshot contains a workflow."],
        evidence_citations=[
            AnalysisEvidenceCitationSchema(
                kind="known_fact",
                subject="The screenshot contains a workflow.",
                block_ids=["image-block"],
            )
        ],
    )
    enabled = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=True,
    )

    enabled.analyze_evidence(requirement, (), (document,), (), ())  # type: ignore[arg-type]

    assert client.parse.call_args.kwargs["images"] == (("image/png", b"safe-image-bytes"),)


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_structured_analysis_repairs_missing_citations_without_rewriting_content(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(
            known_facts=["Bundles are ordered in the portal."],
            constraints=["Only portal orders are supported."],
        ),
        IndexedAnalysisEvidenceRecoverySchema(
            decisions=[
                IndexedAnalysisEvidenceDecisionSchema(
                    output_number=1,
                    supported=True,
                    block_numbers=[1],
                ),
                IndexedAnalysisEvidenceDecisionSchema(
                    output_number=2,
                    supported=True,
                    block_numbers=[1],
                ),
            ]
        ),
    ]
    trace = MagicMock()
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
        debug_trace=trace,
    )

    result = analyzer.analyze_evidence(
        requirement,
        (),
        (_structured_document(),),
        (),
        (),
    )

    assert result["known_facts"] == ["Bundles are ordered in the portal."]
    assert result["constraints"] == ["Only portal orders are supported."]
    assert set(result["evidence_references"]) == {
        "known_fact:bundles are ordered in the portal.",
        "constraint:only portal orders are supported.",
    }
    assert client.parse.call_count == 2
    assert issubclass(
        client.parse.call_args.kwargs["schema_type"], IndexedAnalysisEvidenceRecoverySchema
    )
    repair_prompt = client.parse.call_args.kwargs["user_prompt"]
    assert "There are exactly 2 outputs" in repair_prompt
    assert "allowed output_number values are 1 through\n2" in repair_prompt
    assert "There are exactly 1 evidence blocks" in repair_prompt
    assert "allowed block_numbers values are 1\nthrough 1" in repair_prompt
    assert "1. [known_fact] Bundles are ordered" in repair_prompt
    events = [call.args[0] for call in trace.record.call_args_list]
    assert "analysis.citation_repair_started" in events
    assert "analysis.citation_repair_succeeded" in events


@pytest.mark.parametrize(
    ("recovery", "message"),
    [
        (
            IndexedAnalysisEvidenceRecoverySchema(
                decisions=[
                    IndexedAnalysisEvidenceDecisionSchema(
                        output_number=1,
                        supported=False,
                    )
                ]
            ),
            "remained unusable",
        ),
        (
            IndexedAnalysisEvidenceRecoverySchema(
                decisions=[
                    IndexedAnalysisEvidenceDecisionSchema(
                        output_number=1,
                        supported=True,
                        block_numbers=[2],
                    )
                ]
            ),
            "remained unusable",
        ),
        (
            IndexedAnalysisEvidenceRecoverySchema(
                decisions=[
                    IndexedAnalysisEvidenceDecisionSchema(
                        output_number=1,
                        supported=True,
                        block_numbers=[1],
                    ),
                    IndexedAnalysisEvidenceDecisionSchema(
                        output_number=1,
                        supported=True,
                        block_numbers=[1],
                    ),
                ]
            ),
            "remained unusable",
        ),
    ],
)
@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_structured_analysis_rejects_unusable_citation_repair(
    client_type: MagicMock,
    recovery: IndexedAnalysisEvidenceRecoverySchema,
    message: str,
    requirement: Requirement,
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(known_facts=["Bundles are ordered in the portal."]),
        recovery,
        recovery,
    ]
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    with pytest.raises(RequirementAnalysisGenerationError, match=message):
        analyzer.analyze_evidence(
            requirement,
            (),
            (_structured_document(),),
            (),
            (),
        )

    assert client.parse.call_count == (
        2 if any(not item.supported for item in recovery.decisions) else 3
    )


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_structured_analysis_discards_invented_reviews_when_no_ai_questions_exist(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.return_value = RequirementAnalysisSchema(
        known_facts=["Bundles are ordered in the portal."],
        active_question_reviews=[
            ActiveQuestionReviewSchema(
                question_id="Q1",
                action="retire",
                rationale="Invented review.",
            )
        ],
        evidence_citations=[
            AnalysisEvidenceCitationSchema(
                kind="known_fact",
                subject="Bundles are ordered in the portal.",
                block_ids=["block-1"],
            )
        ],
    )
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    result = analyzer.analyze_evidence(
        requirement,
        (),
        (_structured_document(),),
        (),
        (),
    )

    assert result["question_reviews"] == []
    assert client.parse.call_count == 1


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_structured_analysis_repairs_questions_before_citations(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(
            known_facts=["Bundles are ordered in the portal."],
            active_question_reviews=[
                ActiveQuestionReviewSchema(
                    question_id="Q1",
                    action="retire",
                    rationale="Invented identifier.",
                )
            ],
        ),
        IndexedQuestionReconciliationSchema(
            active_question_reviews=[
                IndexedActiveQuestionReviewSchema(
                    question_number=1,
                    action="retain",
                    rationale="The supported channels are still undefined.",
                )
            ]
        ),
        IndexedAnalysisEvidenceRecoverySchema(
            decisions=[
                IndexedAnalysisEvidenceDecisionSchema(
                    output_number=1,
                    supported=True,
                    block_numbers=[1],
                ),
                IndexedAnalysisEvidenceDecisionSchema(
                    output_number=2,
                    supported=True,
                    block_numbers=[1],
                ),
            ]
        ),
    ]
    active_question = ActiveQuestionContext(
        question_id="question-stable-1",
        kind=ClarificationKind.OPEN_QUESTION,
        subject="Which channels support bundle ordering?",
        rationale="The supported channels are not defined.",
        source=ClarificationSource.AI,
    )
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    result = analyzer.analyze_evidence(
        requirement,
        (),
        (_structured_document(),),
        (),
        (active_question,),
    )

    assert result["question_reviews"][0]["question_id"] == "question-stable-1"
    assert set(result["evidence_references"]) == {
        "known_fact:bundles are ordered in the portal.",
        "open_question:which channels support bundle ordering?",
    }
    assert [call.kwargs["schema_type"] for call in client.parse.call_args_list] == [
        RequirementAnalysisSchema,
        IndexedQuestionReconciliationSchema,
        client.parse.call_args_list[-1].kwargs["schema_type"],
    ]
    assert issubclass(
        client.parse.call_args_list[-1].kwargs["schema_type"], IndexedAnalysisEvidenceRecoverySchema
    )


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_structured_analysis_repairs_blank_uncertainty_rationales(
    client_type: MagicMock, requirement: Requirement
) -> None:
    subject = "Which channels support bundle ordering?"
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(
            known_facts=["Bundles are ordered in the portal."],
            new_uncertainties=[
                UncertaintySchema(
                    kind=ClarificationKind.OPEN_QUESTION,
                    subject=subject,
                    rationale=" ",
                )
            ],
            evidence_citations=[
                AnalysisEvidenceCitationSchema(
                    kind="known_fact",
                    subject="Bundles are ordered in the portal.",
                    block_ids=["block-1"],
                ),
                AnalysisEvidenceCitationSchema(
                    kind="open_question",
                    subject=subject,
                    block_ids=["block-1"],
                ),
            ],
        ),
        IndexedUncertaintyRationaleRecoverySchema(
            rationales=[
                IndexedUncertaintyRationaleSchema(
                    uncertainty_number=1,
                    rationale="The source does not identify every supported ordering channel.",
                )
            ]
        ),
    ]
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    result = analyzer.analyze_evidence(
        requirement,
        (),
        (_structured_document(),),
        (),
        (),
    )

    assert result["open_questions"] == [
        {
            "question": subject,
            "rationale": "The source does not identify every supported ordering channel.",
        }
    ]
    assert [call.kwargs["schema_type"] for call in client.parse.call_args_list] == [
        RequirementAnalysisSchema,
        IndexedUncertaintyRationaleRecoverySchema,
    ]


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_structured_analysis_rejects_incomplete_rationale_repair(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(
            known_facts=["Bundles are ordered in the portal."],
            new_uncertainties=[
                UncertaintySchema(
                    kind=ClarificationKind.AMBIGUITY,
                    subject="Channel scope is unclear.",
                    rationale="",
                )
            ],
        ),
        IndexedUncertaintyRationaleRecoverySchema(
            rationales=[
                IndexedUncertaintyRationaleSchema(
                    uncertainty_number=2,
                    rationale="Invalid out-of-range item.",
                )
            ]
        ),
    ]
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    with pytest.raises(RequirementAnalysisGenerationError, match="rationale repair remained"):
        analyzer.analyze_evidence(
            requirement,
            (),
            (_structured_document(),),
            (),
            (),
        )

    assert client.parse.call_count == 2


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_citation_repair_resends_image_evidence(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(known_facts=["The image shows the bundle workflow."]),
        IndexedAnalysisEvidenceRecoverySchema(
            decisions=[
                IndexedAnalysisEvidenceDecisionSchema(
                    output_number=1,
                    supported=True,
                    block_numbers=[1],
                )
            ]
        ),
    ]
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=True,
    )

    analyzer.analyze_evidence(
        requirement,
        (),
        (_structured_document(with_image=True),),
        (),
        (),
    )

    expected_images = (("image/png", b"safe-image-bytes"),)
    assert client.parse.call_args_list[0].kwargs["images"] == expected_images
    assert client.parse.call_args_list[1].kwargs["images"] == expected_images


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_analysis_runs_focused_review_for_undefined_terms(
    client_type: MagicMock,
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(
            known_facts=["A source account is used."],
            business_rules=["Source account must be valid."],
        ),
        ClarificationReviewSchema(
            open_questions=[
                OpenQuestionSchema(
                    question="What criteria define a valid source account?",
                    rationale="The validation criteria are not stated.",
                )
            ]
        ),
    ]
    requirement = Requirement(
        id=RequirementId("req-vague"),
        title=RequirementTitle("Transfer funds"),
        description=RequirementDescription(
            "The source account must be valid and have enough funds."
        ),
        status=RequirementStatus.DRAFT,
        desired_outcome=RequirementContext("Customers can transfer funds."),
    )
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    result = analyzer.analyze(requirement, ())

    assert result["business_rules"] == ["Source account must be valid."]
    assert result["open_questions"] == [
        {
            "question": "What criteria define a valid source account?",
            "rationale": "The validation criteria are not stated.",
        }
    ]
    assert client.parse.call_count == 2
    assert client.parse.call_args.kwargs["schema_type"] is ClarificationReviewSchema


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_analysis_skips_focused_review_without_vague_terms(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.parse.return_value = RequirementAnalysisSchema(
        known_facts=["Bundles are requested in the portal."],
        business_rules=["Bundles can be ordered in the portal."],
    )
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    result = analyzer.analyze(requirement, ())

    assert result["open_questions"] == []
    client.parse.assert_called_once()


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_analysis_runs_focused_outcome_review_when_source_has_no_outcome(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(known_facts=["Bundles are requested in the portal."]),
        DesiredOutcomeReviewSchema(
            can_infer=True,
            statement="Customers can order the requested bundles in the portal.",
            rationale="The business need requests portal ordering.",
            success_measures=["An eligible order can be completed."],
            blocker_question="",
            blocker_rationale="",
        ),
    ]
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    result = analyzer.analyze(replace(requirement, desired_outcome=None), ())

    assert result["intent_proposals"] == [
        {
            "kind": "desired_outcome",
            "statement": "Customers can order the requested bundles in the portal.",
            "rationale": "The business need requests portal ordering.",
            "success_measures": ["An eligible order can be completed."],
        }
    ]
    assert client.parse.call_count == 2
    assert client.parse.call_args.kwargs["schema_type"] is DesiredOutcomeReviewSchema


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_outcome_review_returns_a_blocker_when_inference_is_unsafe(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(known_facts=["The business asks for an improvement."]),
        DesiredOutcomeReviewSchema(
            can_infer=False,
            statement="",
            rationale="",
            blocker_question="What observable result should this business need achieve?",
            blocker_rationale="The source does not define the intended result.",
        ),
    ]
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    result = analyzer.analyze(replace(requirement, desired_outcome=None), ())

    assert result["intent_proposals"] == []
    assert result["open_questions"] == [
        {
            "question": "What observable result should this business need achieve?",
            "rationale": "The source does not define the intended result.",
        }
    ]


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_clarification_retries_empty_delta_as_complete_analysis(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(known_facts=[""]),
        RequirementAnalysisSchema(
            known_facts=["A transfer uses a source balance."],
            constraints=["Source balance must be checked before transfer."],
        ),
    ]
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    result = analyzer.analyze(
        requirement,
        (
            HumanClarification(
                ClarificationKind.OPEN_QUESTION,
                "Which fraud rules apply?",
                "Use the configured fraud policy.",
            ),
        ),
    )

    assert result["constraints"] == ["Source balance must be checked before transfer."]
    assert client.parse.call_count == 2
    assert "COMPLETE replacement analysis" in client.parse.call_args.kwargs["system_prompt"]


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_clarification_reports_empty_completeness_retry(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(known_facts=[""]),
        RequirementAnalysisSchema(known_facts=[""]),
    ]
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    with pytest.raises(
        RequirementAnalysisGenerationError,
        match="after one completeness retry",
    ):
        analyzer.analyze(
            requirement,
            (
                HumanClarification(
                    ClarificationKind.OPEN_QUESTION,
                    "Which fraud rules apply?",
                    "Use the configured fraud policy.",
                ),
            ),
        )


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_reanalysis_recovers_question_reconciliation_with_focused_request(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(
            known_facts=["Bundles are requested in the portal."],
            active_question_reviews=[],
        ),
        IndexedQuestionReconciliationSchema(
            active_question_reviews=[
                IndexedActiveQuestionReviewSchema(
                    question_number=1,
                    action="retain",
                    rationale="The responsible owner is still unknown.",
                )
            ]
        ),
    ]
    active_question = ActiveQuestionContext(
        question_id="q-1",
        kind=ClarificationKind.OPEN_QUESTION,
        subject="Who owns order fallout?",
        rationale="Ownership is not defined.",
        source=ClarificationSource.AI,
    )
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    result = analyzer.analyze(requirement, (), active_questions=(active_question,))

    assert result["question_reviews"] == [
        {
            "question_id": "q-1",
            "action": "retained",
            "rationale": "The responsible owner is still unknown.",
            "replacement": None,
        }
    ]
    assert client.parse.call_count == 2
    assert client.parse.call_args.kwargs["schema_type"] is IndexedQuestionReconciliationSchema


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_reanalysis_rejects_malformed_focused_reconciliation(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(
            known_facts=["Bundles are requested in the portal."],
            active_question_reviews=[],
        ),
        IndexedQuestionReconciliationSchema(
            active_question_reviews=[
                IndexedActiveQuestionReviewSchema(
                    question_number=1,
                    action="replace",
                    rationale="The question needs revision.",
                )
            ]
        ),
    ]
    active_question = ActiveQuestionContext(
        question_id="q-1",
        kind=ClarificationKind.OPEN_QUESTION,
        subject="Who owns order fallout?",
        rationale="Ownership is not defined.",
        source=ClarificationSource.AI,
    )
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    with pytest.raises(
        RequirementAnalysisGenerationError,
        match="remained unusable after focused recovery",
    ):
        analyzer.analyze(requirement, (), active_questions=(active_question,))


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_reanalysis_with_only_human_questions_uses_complete_analysis_retry(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(known_facts=[" "]),
        RequirementAnalysisSchema(known_facts=["Bundles are requested in the portal."]),
    ]
    human_question = ActiveQuestionContext(
        question_id="human-1",
        kind=ClarificationKind.OPEN_QUESTION,
        subject="Who approves launch?",
        rationale=None,
        source=ClarificationSource.HUMAN,
    )
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    result = analyzer.analyze(requirement, (), active_questions=(human_question,))

    assert result["known_facts"] == ["Bundles are requested in the portal."]
    assert client.parse.call_count == 2
    assert "COMPLETE replacement analysis" in client.parse.call_args.kwargs["system_prompt"]


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_initial_analysis_retries_empty_content_once(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.side_effect = [
        RequirementAnalysisSchema(known_facts=[""]),
        RequirementAnalysisSchema(known_facts=["Bundles are requested in the portal."]),
    ]
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    result = analyzer.analyze(requirement, ())

    assert result["known_facts"] == ["Bundles are requested in the portal."]
    assert client.parse.call_count == 2
    assert "COMPLETE replacement analysis" in client.parse.call_args.kwargs["system_prompt"]


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_analysis_rejects_no_usable_content(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client_type.return_value.model = "local-model"
    client_type.return_value.parse.side_effect = [
        RequirementAnalysisSchema(known_facts=["  "]),
        RequirementAnalysisSchema(known_facts=[""]),
    ]
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    with pytest.raises(RequirementAnalysisGenerationError, match="after one completeness retry"):
        analyzer.analyze(requirement, ())


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_local_analysis_maps_transport_failure(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client_type.return_value.parse.side_effect = LocalLLMError("offline")
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )

    with pytest.raises(RequirementAnalysisGenerationError, match="offline"):
        analyzer.analyze(requirement, ())


@patch(
    "smb_requirement_agent.breakdown.infrastructure.llm.local_epic_generator.LocalStructuredOutputClient"
)
def test_local_epic_maps_content_and_provenance(
    client_type: MagicMock,
    requirement: Requirement,
    analysis: RequirementAnalysis,
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.return_value = EpicSchema(
        name="  Bundle offer  ",
        outcome="Bundles can be ordered",
        business_case="Supports the stated offer",
    )

    result = LocalEpicGenerator(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
    ).generate(requirement, analysis)

    assert result["name"] == "Bundle offer"
    assert result["model"] == "local-model"
    prompt = client.parse.call_args.kwargs["user_prompt"]
    assert prompt.index("NOT CONFIRMED") < prompt.index("Billing supports bundles")


@patch(
    "smb_requirement_agent.breakdown.infrastructure.llm.local_epic_generator.LocalStructuredOutputClient"
)
def test_local_epic_rejects_blank_field(
    client_type: MagicMock,
    requirement: Requirement,
    analysis: RequirementAnalysis,
) -> None:
    client_type.return_value.parse.return_value = EpicSchema(
        name=" ", outcome="Outcome", business_case="Case"
    )
    generator = LocalEpicGenerator(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
    )

    with pytest.raises(EpicGenerationError, match="name"):
        generator.generate(requirement, analysis)


@patch(
    "smb_requirement_agent.breakdown.infrastructure.llm.local_epic_generator.LocalStructuredOutputClient"
)
def test_local_epic_maps_transport_failure(
    client_type: MagicMock,
    requirement: Requirement,
    analysis: RequirementAnalysis,
) -> None:
    client_type.return_value.parse.side_effect = LocalLLMError("offline")
    generator = LocalEpicGenerator(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
    )

    with pytest.raises(EpicGenerationError, match="offline"):
        generator.generate(requirement, analysis)


@patch(
    "smb_requirement_agent.breakdown.infrastructure.llm.local_feature_generator.LocalStructuredOutputClient"
)
def test_local_features_drop_blank_items_and_preserve_provenance(
    client_type: MagicMock,
    requirement: Requirement,
    analysis: RequirementAnalysis,
    epic: Epic,
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    client.parse.return_value = FeatureSetSchema(
        features=[
            FeatureItemSchema(
                name=" ",
                outcome="Ignored",
                delivery_drop="mvp",
                splitting_pattern="journey_stage",
                splitting_rationale="Ignored",
            ),
            FeatureItemSchema(
                name=" Ordering ",
                outcome="Order bundles",
                delivery_drop="mvp",
                splitting_pattern="journey_stage",
                splitting_rationale="Separate journey step",
            ),
        ]
    )

    result = LocalFeatureGenerator(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
    ).generate(requirement, analysis, epic)

    assert [candidate["name"] for candidate in result] == ["Ordering"]
    assert result[0]["model"] == "local-model"


@patch(
    "smb_requirement_agent.breakdown.infrastructure.llm.local_feature_generator.LocalStructuredOutputClient"
)
def test_local_features_reject_empty_result(
    client_type: MagicMock,
    requirement: Requirement,
    analysis: RequirementAnalysis,
    epic: Epic,
) -> None:
    client_type.return_value.parse.return_value = FeatureSetSchema()
    generator = LocalFeatureGenerator(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
    )

    with pytest.raises(FeatureGenerationError, match="no usable Features"):
        generator.generate(requirement, analysis, epic)


@patch(
    "smb_requirement_agent.breakdown.infrastructure.llm.local_feature_generator.LocalStructuredOutputClient"
)
def test_local_features_map_transport_failure(
    client_type: MagicMock,
    requirement: Requirement,
    analysis: RequirementAnalysis,
    epic: Epic,
) -> None:
    client_type.return_value.parse.side_effect = LocalLLMError("offline")
    generator = LocalFeatureGenerator(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
    )

    with pytest.raises(FeatureGenerationError, match="offline"):
        generator.generate(requirement, analysis, epic)


@patch(
    "smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer.LocalStructuredOutputClient"
)
def test_citation_repair_preserves_more_than_eight_required_source_blocks(
    client_type: MagicMock, requirement: Requirement
) -> None:
    client = client_type.return_value
    client.model = "local-model"
    statement = "The system comprises nine layers."
    client.parse.side_effect = [
        RequirementAnalysisSchema(known_facts=[statement]),
        IndexedAnalysisEvidenceRecoverySchema.model_validate_json(
            json.dumps(
                {
                    "decisions": [
                        {"output_number": 1, "supported": True, "block_numbers": list(range(1, 10))}
                    ]
                }
            ),
            strict=True,
        ),
    ]
    document = _structured_document()
    document["evidence_blocks"] = [
        AnalysisEvidenceBlock(
            block_id=f"layer-{number}",
            kind="paragraph",
            section_path=[],
            label=f"Layer {number}",
            text=f"Layer {number}",
            asset_id=None,
        )
        for number in range(1, 10)
    ]
    analyzer = LocalRequirementAnalyzer(
        base_url="http://127.0.0.1:1234/v1",
        http_client=httpx.Client(),
        model="local-model",
        timeout_seconds=90,
        reasoning_effort=None,
        vision_enabled=False,
    )
    result = analyzer.analyze_evidence(requirement, (), (document,), (), ())
    assert result["known_facts"] == [statement]
    references = result["evidence_references"]["known_fact:the system comprises nine layers."]
    assert [reference["block_id"] for reference in references] == [
        f"layer-{number}" for number in range(1, 10)
    ]
    assert all(
        reference["document_id"] == document["document_id"]
        and reference["version_id"] == document["version_id"]
        for reference in references
    )
    assert client.parse.call_count == 2
