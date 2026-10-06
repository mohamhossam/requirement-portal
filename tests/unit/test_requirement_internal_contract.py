"""Requirement work's internal API matches its committed contract (ADR-0099).

`contracts/requirement-internal.openapi.json` is what the knowledge service
builds its adapters against; knowledge-portal pins a copy and tests against it.
"""

from __future__ import annotations

import json
from pathlib import Path

from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.interfaces.api.routes.internal import contract_openapi

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "requirement-internal.openapi.json"


def test_the_internal_api_matches_its_committed_contract() -> None:
    committed = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(contract_openapi(), sort_keys=True)), (
        "contracts/requirement-internal.openapi.json is stale; regenerate it from "
        "contract_openapi() and review the change with the knowledge service."
    )


def test_the_contract_covers_what_the_knowledge_service_reads_and_stays_private() -> None:
    paths = set(json.loads(CONTRACT.read_text(encoding="utf-8"))["paths"])
    assert paths == {
        "/internal/references/{document_id}/impact",
        "/internal/references/{document_id}/dependents",
        "/internal/architecture-mapping/stats",
        "/internal/knowledge/corpus/summary",
        "/internal/knowledge/corpus",
        "/internal/knowledge/findings",
        "/internal/knowledge/findings/{finding_id}/nudge",
    }
    public = create_app().openapi()["paths"]
    assert not paths & set(public)
