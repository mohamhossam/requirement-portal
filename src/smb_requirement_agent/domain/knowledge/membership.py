"""A Requirement's membership of the knowledge corpus (Knowledge Center B3).

A knowledge admin retires an obsolete or cancelled Requirement from the corpus, with a reason.
A retired Requirement stays fully readable and keeps its history, but takes no part in
screening, knowledge search or answer suggestions until it is reinstated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from smb_requirement_agent.references.domain.errors import InvalidKnowledgeError
from smb_requirement_agent.shared_kernel.actors import ActorSnapshot
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.staleness import require_aware

REASON_MAX = 500


def corpus_reason(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise InvalidKnowledgeError("Say why: a corpus action needs a reason.")
    if len(cleaned) > REASON_MAX:
        raise InvalidKnowledgeError(f"A reason is at most {REASON_MAX} characters.")
    return cleaned


class CorpusState(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


@dataclass(frozen=True)
class CorpusMembership:
    """The last corpus action on a Requirement: who retired or reinstated it, when and why.

    A Requirement no admin has acted on has no membership record and is active.
    """

    requirement_id: RequirementId
    state: CorpusState
    reason: str
    actor: ActorSnapshot
    changed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", corpus_reason(self.reason))
        require_aware(self.changed_at, "corpus membership changed_at")

    @property
    def retired(self) -> bool:
        return self.state is CorpusState.RETIRED


class CorpusActionKind(StrEnum):
    RETIRE = "retire"
    REINSTATE = "reinstate"
    RETRY = "retry"
    REINDEX = "reindex"


@dataclass(frozen=True)
class CorpusAction:
    """One knowledge admin's action on the corpus, as its audit trail records it."""

    action_id: str
    kind: CorpusActionKind
    requirement_ids: tuple[RequirementId, ...]
    actor: ActorSnapshot
    reason: str | None
    acted_at: datetime

    def __post_init__(self) -> None:
        if self.reason is not None:
            object.__setattr__(self, "reason", corpus_reason(self.reason))
        require_aware(self.acted_at, "corpus action acted_at")
