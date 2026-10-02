"""The knowledge service's internal API matches its committed contract (ADR-0099).

`contracts/knowledge-internal.openapi.json` is what requirement work's HTTP
adapters are built against. Stage 3 copies it into knowledge-portal, whose
provider tests then hold the moved service to the same file.
"""

from __future__ import annotations

import json
from pathlib import Path

from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.knowledge_internal.app import create_knowledge_internal_app

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "knowledge-internal.openapi.json"


def test_the_internal_api_matches_its_committed_contract() -> None:
    app = create_knowledge_internal_app(build_container, "x" * 40)
    committed = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(app.openapi(), sort_keys=True)), (
        "contracts/knowledge-internal.openapi.json is stale; regenerate it from "
        "create_knowledge_internal_app(...).openapi() and review the change with both services."
    )


def test_the_contract_covers_every_seam_requirement_work_uses() -> None:
    paths = json.loads(CONTRACT.read_text(encoding="utf-8"))["paths"]
    assert set(paths) == {
        "/internal/architecture/match",
        "/internal/library/published",
        "/internal/library/search",
        "/internal/library/retrieve",
        "/internal/events",
    }
