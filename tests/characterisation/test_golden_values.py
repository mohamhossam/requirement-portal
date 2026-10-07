"""Behaviour the bounded-context migration must preserve byte for byte (ADR-0103, PR 1).

- Persisted JSONB payloads: a changed payload breaks stored rows or silently rewrites them.
- ADR-0021 fingerprints: a changed fingerprint makes every existing approval non-current.
- Expected-context tokens: a changed token rejects requests from clients already holding one.
- The review policy's output: moving it into the governance domain must not change a flag.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from tests.characterisation import cases, golden

VALUES = golden.all_values()


@pytest.mark.parametrize("name", sorted(VALUES))
def test_value_matches_golden(name: str) -> None:
    compute: Callable[[], object] = VALUES[name]

    assert golden.render(compute()) == golden.read(name)


@pytest.mark.parametrize("name", sorted(cases.PAYLOAD_CASES))
def test_golden_payload_decodes_to_the_sample(name: str) -> None:
    """Rows written before the migration still load into the same aggregate."""
    case = cases.PAYLOAD_CASES[name]
    stored = json.loads(golden.read(f"payloads/{name}"))

    assert case.decode(stored) == case.sample()


@pytest.mark.parametrize("name", sorted(cases.PAYLOAD_CASES))
def test_golden_payload_reencodes_unchanged(name: str) -> None:
    """Loading and saving a stored row writes it back unchanged."""
    case = cases.PAYLOAD_CASES[name]
    stored = json.loads(golden.read(f"payloads/{name}"))

    assert case.encode(case.decode(stored)) == stored


def test_every_golden_file_is_checked() -> None:
    """A golden file nobody compares is not protecting anything."""
    on_disk = {
        str(path.relative_to(golden.GOLDEN_DIR).with_suffix("")).replace("\\", "/")
        for path in golden.GOLDEN_DIR.rglob("*.json")
    }

    assert on_disk == set(VALUES)
