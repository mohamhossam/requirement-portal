"""Opt-in single-file diagnostic trace coverage."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from smb_kernel.diagnostics import (
    JsonLinesDebugTrace,
    NullDebugTrace,
)
from smb_kernel.llm.local_structured_output import (
    LocalStructuredOutputClient,
)

from smb_requirement_agent.analysis.infrastructure.llm.analysis_mappers import to_analysis_candidate
from smb_requirement_agent.analysis.infrastructure.llm.schemas.analysis_schema import (
    AnalysisEvidenceCitationSchema,
    RequirementAnalysisSchema,
)
from smb_requirement_agent.application.errors import RequirementAnalysisGenerationError
from smb_requirement_agent.breakdown.infrastructure.llm.schemas.epic_schema import EpicSchema


def _events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _details_by_event(path: Path, event: str) -> dict[str, Any]:
    return next(item["details"] for item in _events(path) if item["event"] == event)


def test_null_trace_performs_no_file_io(tmp_path: Path) -> None:
    trace = NullDebugTrace()

    trace.record("ignored", path=str(tmp_path / "should-not-exist.log"))
    trace.close()

    assert trace.enabled is False
    assert list(tmp_path.iterdir()) == []


def test_json_lines_trace_redacts_secrets_binary_images_and_reasoning(tmp_path: Path) -> None:
    path = tmp_path / "debug.log"
    trace = JsonLinesDebugTrace(str(path))

    trace.record(
        "redaction.check",
        authorization="Bearer private",
        openai_api_key="sk-private",
        max_tokens=8192,
        binary=b"image-bytes",
        image_url="data:image/png;base64,cHJpdmF0ZQ==",
        reasoning="hidden chain",
        prompt="Visible requirement text",
    )
    logging.getLogger("smb_requirement_agent.test").warning("Worker event %s", "job-1")
    trace.close()

    details = _details_by_event(path, "redaction.check")
    assert details["authorization"] == "[REDACTED]"
    assert details["openai_api_key"] == "[REDACTED]"
    assert details["max_tokens"] == 8192
    assert str(details["binary"]).startswith("[REDACTED: 11 binary bytes;")
    assert details["image_url"] == "[REDACTED: image/png data URL]"
    assert details["reasoning"] == "[REDACTED: hidden reasoning]"
    assert details["prompt"] == "Visible requirement text"
    python_log = _details_by_event(path, "python.log")
    assert python_log["message"] == "Worker event job-1"


def test_local_client_traces_request_raw_response_and_parsed_model(tmp_path: Path) -> None:
    path = tmp_path / "debug.log"
    trace = JsonLinesDebugTrace(str(path))
    completion = json.dumps(
        {
            "name": "SMB Bundle Offer",
            "outcome": "Bundles can be ordered",
            "business_case": "Supports the stated offer",
        }
    )
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [{"message": {"content": completion, "reasoning": "hidden chain"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 30},
    }
    client = LocalStructuredOutputClient(
        base_url="http://127.0.0.1:11434/v1",
        http_client=httpx.Client(),
        model="qwen3-vl:8b",
        timeout_seconds=90,
        reasoning_effort="none",
        debug_trace=trace,
    )

    with patch(
        "smb_kernel.llm.local_structured_output.httpx.Client.post",
        return_value=response,
    ):
        result = client.parse(
            system_prompt="System rules",
            user_prompt="Requirement text",
            schema_type=EpicSchema,
        )
    trace.close()

    assert result.name == "SMB Bundle Offer"
    request = _details_by_event(path, "local_llm.request")
    request_body = request["request_body"]
    assert isinstance(request_body, dict)
    assert request_body["messages"][0]["content"] == "System rules"
    assert request_body["messages"][1]["content"] == "Requirement text"
    raw_response = _details_by_event(path, "local_llm.response")
    payload = raw_response["payload"]
    assert isinstance(payload, dict)
    assert payload["choices"][0]["message"]["content"] == completion
    assert payload["choices"][0]["message"]["reasoning"] == "[REDACTED: hidden reasoning]"
    parsed = _details_by_event(path, "local_llm.parsed")
    assert parsed["parsed"]["name"] == "SMB Bundle Offer"


def test_analysis_trace_identifies_the_exact_missing_citation_key(tmp_path: Path) -> None:
    path = tmp_path / "debug.log"
    trace = JsonLinesDebugTrace(str(path))
    parsed = RequirementAnalysisSchema(
        known_facts=["BFM bundles support DEL."],
        constraints=["DEL is limited to eligible customers."],
        evidence_citations=[
            AnalysisEvidenceCitationSchema(
                kind="known_fact",
                subject="BFM bundles support DEL.",
                block_ids=["block-17"],
            )
        ],
    )
    document = {
        "document_id": "document-1",
        "version_id": "version-1",
        "filename": "source.docx",
        "checksum_sha256": "a" * 64,
        "extracted_text": "Evidence",
        "evidence_blocks": [
            {
                "block_id": "block-17",
                "kind": "paragraph",
                "section_path": ["Scope"],
                "label": "Scope statement",
                "text": "BFM bundles support DEL for eligible customers.",
                "asset_id": None,
            }
        ],
        "image_assets": [],
    }

    with pytest.raises(RequirementAnalysisGenerationError, match="cite every"):
        to_analysis_candidate(
            parsed,
            model="qwen3-vl:8b",
            prompt_version="analysis-v5-structured-evidence",
            documents=(document,),  # type: ignore[arg-type]
            debug_trace=trace,
        )
    trace.close()

    comparison = _details_by_event(path, "analysis_mapper.citation_comparison")
    assert comparison["returned_keys"] == ["known_fact:bfm bundles support del."]
    assert comparison["missing_keys"] == ["constraint:del is limited to eligible customers."]
