"""Evaluate human judgments and validated retrieval exports. Nonzero exit means not qualified."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from pydantic import TypeAdapter

from smb_requirement_agent.references.application.retrieval_evaluation import (
    EvaluationQuery,
    QueryResult,
    evaluate_retrieval,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("judgments", type=Path)
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    queries = TypeAdapter(tuple[EvaluationQuery, ...]).validate_json(args.judgments.read_bytes())
    results = TypeAdapter(tuple[QueryResult, ...]).validate_json(args.results.read_bytes())
    report = evaluate_retrieval(queries, results)
    print(json.dumps(asdict(report), indent=2))
    return 0 if report.quality_gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
