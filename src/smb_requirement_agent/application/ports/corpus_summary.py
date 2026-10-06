"""How large the Requirement knowledge corpus is, and which findings stand open (A′)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class CorpusCounts:
    # Every Requirement, including those closed as duplicates.
    requirements: int
    # Closed as a duplicate: indexed with no passages, so never a candidate.
    duplicates: int
    # When each finding still in force was raised: actionable, with both
    # Requirements at the versions it judged (the Knowledge step's own rule).
    open_findings_raised_at: tuple[datetime, ...]


class CorpusCountsPort(Protocol):
    def counts(self) -> CorpusCounts:
        """Counts and times only; never which Requirements, so no membership is needed."""
        ...
