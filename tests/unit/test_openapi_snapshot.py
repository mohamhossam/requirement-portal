"""The committed browser contract must match the running API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from smb_requirement_agent.interfaces.api.main import app

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "frontend" / "openapi.json"


def test_openapi_snapshot_matches_application() -> None:
    committed: dict[str, Any] = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    assert committed == app.openapi(), (
        "frontend/openapi.json is stale; run "
        ".venv/Scripts/python scripts/dump_openapi.py and regenerate the TypeScript client."
    )


def test_review_values_are_closed_enums_in_openapi() -> None:
    schemas = app.openapi()["components"]["schemas"]

    assert schemas["GenerationStatus"]["enum"] == [
        "generated",
        "edited",
        "needs_revision",
        "approved",
    ]
    assert schemas["StaleReason"]["enum"] == [
        "requirement_changed",
        "epic_changed",
        "feature_changed",
    ]
    assert schemas["DeliveryDrop"]["enum"] == ["mvp", "later"]
    assert schemas["SplittingPattern"]["enum"] == [
        "component_system",
        "journey_stage",
        "mvp_vs_later",
        "channel",
        "business_variant",
    ]
