"""Run with a human-reviewed JSON list; synthetic cases are not release evidence."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from pydantic import TypeAdapter

from smb_requirement_agent.application.grounding_evaluation import (
    GroundingJudgment,
    evaluate_grounding,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("judgments", type=Path)
    args = parser.parse_args()
    values = TypeAdapter(tuple[GroundingJudgment, ...]).validate_json(args.judgments.read_text())
    print(json.dumps(asdict(evaluate_grounding(values)), indent=2))


if __name__ == "__main__":
    main()
