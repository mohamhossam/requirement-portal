"""Opt-in live embedding qualification; synthetic in-memory corpus, no application data.

Run with -m tests.live_model_rollout --config ... --target-model ... .
Never collected by pytest; credentials are resolved only through Settings.
"""

import argparse
import json
from datetime import UTC, datetime

from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.composition.operations import (
    reference_model_qualification,
)
from tests.indexing_contracts import exercise_owner_rollout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--target-model", required=True)
    args = parser.parse_args()
    settings = Settings.from_env(config_path=args.config)
    assert settings.llm_profiles is not None
    with reference_model_qualification(settings, args.target_model) as (library, first, second):
        exercise_owner_rollout(library, first, second)
        print(
            json.dumps(
                {
                    "measured_at": datetime.now(UTC).isoformat(),
                    "source_model": settings.llm_profiles.selected_embedding.model,
                    "target_model": args.target_model,
                    "source_identity": first.identity,
                    "target_identity": second.identity,
                    "owners": 2,
                    "documents": 2,
                    "result": "passed",
                    "checks": [
                        "owner authority",
                        "all-owner readiness gate",
                        "model identity isolation",
                        "activation",
                        "rollback by reviewed rebuild",
                        "excluded text",
                        "old citation staleness",
                        "immutable extraction/review history",
                    ],
                    "scope": (
                        "Live providers with synthetic in-memory corpus; "
                        "deployed maintenance still required."
                    ),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
