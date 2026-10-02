"""Explicit, reproducible model-token measurements for approved synthetic fixtures."""

import hashlib
from dataclasses import asdict, dataclass

from smb_requirement_agent.application.ports.embedding import TokenCounterPort


@dataclass(frozen=True)
class ChunkTokenMeasurement:
    case: str
    text_sha256: str
    utf8_budget_units: int
    measured_model_tokens: int
    within_model_limit: bool


def qualify_chunk_tokens(
    counter: TokenCounterPort,
    samples: tuple[tuple[str, str], ...],
    input_limit: int,
) -> dict[str, object]:
    if input_limit < 1 or not samples or any(not text.strip() for _, text in samples):
        raise ValueError("Qualification requires nonblank samples and a positive model limit.")
    measurements = tuple(
        ChunkTokenMeasurement(
            case,
            hashlib.sha256(text.encode()).hexdigest(),
            len(text.encode()),
            tokens,
            tokens <= input_limit,
        )
        for case, text in samples
        for tokens in (counter.count(text),)
    )
    return {
        "counter_identity": counter.identity,
        "model_input_limit": input_limit,
        "sample_count": len(measurements),
        "all_within_model_limit": all(m.within_model_limit for m in measurements),
        "measurements": [asdict(m) for m in measurements],
        "scope": (
            "Measured fixture safety only; not retrieval relevance "
            "or universal tokenizer equivalence."
        ),
    }
