"""Read, compare and (deliberately) rewrite the golden files.

The golden files are the record of what the code produced before the bounded-context migration
began. They are compared byte for byte. Rewriting them is a decision, not a fix: it means a
change alters persisted payloads, approval fingerprints or context tokens, and that change
needs its own review and, for fingerprints, a data plan for existing approvals.

To rewrite them after such a decision:

    python -m tests.characterisation.golden
"""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import partial
from pathlib import Path

from tests.characterisation import cases

GOLDEN_DIR = Path(__file__).parent / "golden"


def render(value: object) -> str:
    """The canonical on-disk form: sorted keys, indented, UTF-8, trailing newline."""
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def path_for(name: str) -> Path:
    return GOLDEN_DIR / f"{name}.json"


def read(name: str) -> str:
    path = path_for(name)
    if not path.exists():
        raise AssertionError(
            f"Golden file {path} is missing. "
            "Record it with `python -m tests.characterisation.golden`."
        )
    return path.read_text(encoding="utf-8")


def all_values() -> dict[str, Callable[[], object]]:
    """Every golden file and the function that computes its current value."""
    values: dict[str, Callable[[], object]] = {
        f"payloads/{name}": partial(_encoded, case) for name, case in cases.PAYLOAD_CASES.items()
    }
    values["fingerprints"] = cases.fingerprints
    values["context_tokens"] = cases.context_tokens
    values["review_policy_build"] = cases.built_review
    return values


def _encoded(case: cases.PayloadCase) -> object:
    return case.encode(case.sample())


def rewrite() -> None:
    for name, compute in all_values().items():
        path = path_for(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(compute()), encoding="utf-8")


if __name__ == "__main__":
    rewrite()
