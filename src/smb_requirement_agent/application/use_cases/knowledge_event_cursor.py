"""How far a consumer of the knowledge events may move its cursor (ADR-0099).

Sequence numbers are taken when an event is written, but transactions commit in their
own order, so a later number can be visible while an earlier one is still in flight.
A consumer applies every visible event, but its cursor only moves through an unbroken
run of numbers. A gap older than `gap_grace` is a rolled-back write and is stepped over.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta

from smb_requirement_agent.application.ports.knowledge_events import KnowledgeEvent


def contiguous_reach(
    cursor: int, events: Sequence[KnowledgeEvent], now: datetime, gap_grace: timedelta
) -> int:
    reached = cursor
    for event in events:
        if event.seq != reached + 1 and now - event.created_at < gap_grace:
            break
        reached = event.seq
    return reached
