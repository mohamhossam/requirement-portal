"""The architecture vocabulary requirement work shares with the knowledge service.

The catalogue itself (releases, systems, domains, journeys and its curation)
lives in the knowledge portal (ADR-0099). An architecture impact still names
how systems depend on each other, and a remap can still collide with a
concurrent change, so these few terms stay here.
"""

from __future__ import annotations

from enum import StrEnum


class InvalidRelationshipKindError(ValueError):
    """A relationship kind is not one the catalogue defines.

    Named apart from `domain.knowledge.errors.InvalidKnowledgeError` (ADR-0103, PR 2). It keeps
    its own public code, `invalid_architecture_knowledge`.
    """


class KnowledgeConflictError(Exception):
    """Architecture work changed while it was being acted on."""


class RelationshipKind(StrEnum):
    """How the source system depends on the target, when a source says so."""

    CALLS_API = "calls_api"
    PUBLISHES_EVENTS_TO = "publishes_events_to"
    TRANSFERS_DATA_TO = "transfers_data_to"
    ORCHESTRATES = "orchestrates"
    UNSPECIFIED = "unspecified"


def relationship_kind(value: str | RelationshipKind) -> RelationshipKind:
    """A stored or transported kind; anything unknown is refused, never guessed."""
    try:
        return RelationshipKind(value)
    except ValueError as exc:
        raise InvalidRelationshipKindError(f"Unknown relationship kind {value!r}.") from exc
