"""The base every domain event shares (ADR-0103 §3).

A domain event says that something changed in the context that owns it. It carries
identities only, never aggregates, and is dispatched in process, synchronously, inside the
publisher's unit of work. Events are named in the past tense for what changed, never for what a
consumer will do.
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Something that happened to one Requirement's workspace."""

    requirement_id: RequirementId
