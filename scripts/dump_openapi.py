"""Write the FastAPI OpenAPI contract consumed by the browser client."""

from __future__ import annotations

import json
from pathlib import Path

from smb_requirement_agent.interfaces.api.main import app

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "openapi.json"


def main() -> None:
    OUTPUT.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
