"""Score the configured prior-art judge against labelled cases, before PRIOR_ART_ENABLED.

Uses the same provider settings as the service (LLM_PROVIDER and friends). Synthetic
cases exercise the harness; only human-reviewed cases are release evidence.

    python scripts/evaluate_prior_art.py docs/evaluation/prior-art-synthetic.json
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from pydantic import TypeAdapter
from smb_kernel.observability.metrics import Metrics

from smb_requirement_agent.application.prior_art_evaluation import (
    PriorArtCase,
    evaluate_prior_art,
)
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.composition.llm import build_llm_adapters


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    args = parser.parse_args()
    cases = TypeAdapter(tuple[PriorArtCase, ...]).validate_json(args.cases.read_text())
    adapters = build_llm_adapters(Settings.from_env(), Metrics())
    try:
        result = evaluate_prior_art(cases, adapters.prior_art_judge)
    finally:
        adapters.resources.close()
    print(json.dumps(asdict(result), indent=2))
    raise SystemExit(0 if result.quality_gate_passed else 1)


if __name__ == "__main__":
    main()
